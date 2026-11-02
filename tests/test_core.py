"""Tests der Kernlogik mit einer simulierten SD-Karte.  Aufruf: python -m pytest tests"""
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dcim_import import core  # noqa: E402


def make_jpg(path: Path, shot: str | None, size=(64, 48)):
    from PIL import Image
    im = Image.new("RGB", size, (200, 100, 50))
    exif = Image.Exif()
    if shot:
        exif.get_ifd(0x8769)[36867] = shot
    im.save(path, exif=exif)


def make_card(tmp: Path) -> Path:
    card = tmp / "card"
    d1 = card / "DCIM" / "101OLYMP"
    d2 = card / "DCIM" / "102OLYMP"
    d1.mkdir(parents=True)
    d2.mkdir(parents=True)
    (card / "DCIM" / "MISC").mkdir()  # kein DCF-Ordner
    make_jpg(d1 / "P1010001.JPG", "2026:10:30 10:00:00")
    (d1 / "P1010001.ORF").write_bytes(b"r" * 100)
    make_jpg(d1 / "P1010002.JPG", "2026:10:31 09:00:00")
    (d1 / "P1010002.ORF").write_bytes(b"r" * 120)
    (d1 / "P1010003.ORF").write_bytes(b"r" * 130)   # RAW ohne JPG
    (d1 / "P1010004.MOV").write_bytes(b"v" * 300)
    make_jpg(d2 / "P1010001.JPG", "2026:11:01 12:00:00", size=(80, 60))  # gleicher Name!
    return card


def test_find_and_scan(tmp_path, monkeypatch):
    card_root = make_card(tmp_path)
    monkeypatch.setattr(core, "candidate_roots", lambda: [card_root, tmp_path / "nix"])
    cards = core.find_cards()
    assert len(cards) == 1
    assert [d.name for d in cards[0].dirs] == ["101OLYMP", "102OLYMP"]

    files = core.scan_card(cards[0], read_exif=True)
    assert len(files) == 7
    by = {(f.path.parent.name, f.name): f for f in files}
    assert by[("101OLYMP", "P1010001.JPG")].shot == datetime(2026, 10, 30, 10)
    # RAW übernimmt Datum vom JPG gleichen Namens
    assert by[("101OLYMP", "P1010002.ORF")].shot == datetime(2026, 10, 31, 9)


def test_plan_import_date(tmp_path, monkeypatch):
    card_root = make_card(tmp_path)
    monkeypatch.setattr(core, "candidate_roots", lambda: [card_root])
    files = core.scan_card(core.find_cards()[0], read_exif=False)
    target = tmp_path / "import"
    opt = core.Options(target, suffix=' Headphone: Stand ', split=True, videos_separate=True)
    plan = core.make_plan(files, opt, today=datetime(2026, 11, 2))
    assert plan.folders == [target / "2026-11-02 Headphone Stand"]
    rel = sorted(str(j.dest.relative_to(plan.folders[0])) for j in plan.jobs)
    assert rel == sorted([
        "jpg/P1010001.JPG", "jpg/P1010001_1.JPG", "jpg/P1010002.JPG",
        "raw/P1010001.ORF", "raw/P1010002.ORF", "raw/P1010003.ORF",
        "video/P1010004.MOV"])


def test_plan_by_shot_date(tmp_path, monkeypatch):
    card_root = make_card(tmp_path)
    monkeypatch.setattr(core, "candidate_roots", lambda: [card_root])
    files = core.scan_card(core.find_cards()[0], read_exif=True)
    opt = core.Options(tmp_path / "import", by_shot_date=True)
    plan = core.make_plan(files, opt)
    names = {f.name for f in plan.folders}
    assert {"2026-10-30", "2026-10-31", "2026-11-01"} <= names


def test_run_verify_rerun_and_already(tmp_path, monkeypatch):
    card_root = make_card(tmp_path)
    monkeypatch.setattr(core, "candidate_roots", lambda: [card_root])
    card = core.find_cards()[0]
    target = tmp_path / "import"
    opt = core.Options(target, verify_hash=True)

    files = core.scan_card(card, read_exif=False)
    plan = core.make_plan(files, opt, today=datetime(2026, 11, 1))
    res = core.run_plan(plan, opt)
    assert res.copied == 7 and not res.errors and res.verified

    # gleicher Tag nochmal: keine _1-Duplikate, nichts doppelt
    plan2 = core.make_plan(files, core.Options(target), today=datetime(2026, 11, 1))
    res2 = core.run_plan(plan2, core.Options(target))
    assert res2.skipped_same == 7 and res2.copied == 0
    assert len(list((target / "2026-11-01").rglob("*.*"))) == 7 + 1  # + Aufräum-Script

    # anderer Tag: Hinweis "schon importiert", aber Kopie trotzdem
    plan3 = core.make_plan(files, core.Options(target), today=datetime(2026, 11, 2))
    assert plan3.already == {"2026-11-01": 7}


def test_pairs_and_orphans(tmp_path):
    f = tmp_path / "2026-11-02"
    (f / "jpg").mkdir(parents=True)
    (f / "raw").mkdir()
    for n in ("A", "B"):
        (f / "jpg" / f"{n}.JPG").write_bytes(b"j")
    for n in ("A", "B", "C"):
        (f / "raw" / f"{n}.ORF").write_bytes(b"r")
    pairs = core.pairs_in(f)
    assert [(j.name, [r.name for r in rs]) for j, rs in pairs] == [
        ("A.JPG", ["A.ORF"]), ("B.JPG", ["B.ORF"])]
    assert [p.name for p in core.orphan_raws(f)] == ["C.ORF"]

    # alte Ordner ohne Unterordner funktionieren auch
    g = tmp_path / "flat"
    g.mkdir()
    (g / "X.JPG").write_bytes(b"j")
    (g / "X.ORF").write_bytes(b"r")
    (g / "Y.ORF").write_bytes(b"r")
    assert [p.name for p in core.orphan_raws(g)] == ["Y.ORF"]


def test_folder_name():
    assert core.folder_name("2026-11-02", "") == "2026-11-02"
    assert core.folder_name("2026-11-02", " a/b?. ") == "2026-11-02 ab"


def test_history_skip_and_cleanup_script(tmp_path, monkeypatch):
    card_root = make_card(tmp_path)
    monkeypatch.setattr(core, "candidate_roots", lambda: [card_root])
    files = core.scan_card(core.find_cards()[0], read_exif=False)
    target = tmp_path / "import"
    opt = core.Options(target)
    core.run_plan(core.make_plan(files, opt, today=datetime(2026, 11, 1)), opt)
    folder = target / "2026-11-01"
    assert (folder / core.cleanup_name()).read_bytes().startswith(b"@echo off\r\n")
    assert (target / core.HISTORY_FILE).exists()

    # später aussortiert -> trotzdem als "schon importiert" erkannt (über Historie)
    (folder / "jpg" / "P1010002.JPG").unlink()
    (folder / "raw" / "P1010002.ORF").unlink()
    skip = core.Options(target, skip_already=True)
    plan = core.make_plan(files, skip, today=datetime(2026, 11, 3))
    assert plan.already == {"2026-11-01": 7}
    assert plan.jobs == [] and plan.skipped == 7 and plan.folders == []

    # ohne Überspringen: alles kopiert, Ordner nur für genutzte Ziele
    plan2 = core.make_plan(files, core.Options(target), today=datetime(2026, 11, 3))
    assert len(plan2.jobs) == 7 and plan2.folders == [target / "2026-11-03"]


def test_generic_cameras_and_filter(tmp_path, monkeypatch):
    sony = tmp_path / "sony" / "DCIM" / "100MSDCF"
    sony.mkdir(parents=True)
    (sony / "DSC01234.ARW").write_bytes(b"r")
    make_jpg(sony / "DSC01234.JPG", None)
    fuji = tmp_path / "fuji" / "DCIM" / "101_FUJI"
    fuji.mkdir(parents=True)
    (fuji / "DSCF0001.RAF").write_bytes(b"r")
    monkeypatch.setattr(core, "candidate_roots",
                        lambda: [tmp_path / "sony", tmp_path / "fuji"])
    cards = core.find_cards()
    assert [c.vendor for c in cards] == ["Sony", "Fujifilm"]
    assert {f.kind for f in core.scan_card(cards[0], False)} == {"raw", "jpg"}
    assert [c.vendor for c in core.find_cards(core.parse_only("fuji"))] == ["Fujifilm"]
    assert core.parse_only(" OLYMP, canon;nikon ") == ["OLYMP", "CANON", "NIKON"]
    assert core.kind_of(Path("a.CR3")) == "raw" and core.kind_of(Path("a.NEF")) == "raw"


def test_cleanup_script_has_all_raw_ext(tmp_path):
    core.write_cleanup_script(tmp_path)
    txt = (tmp_path / core.cleanup_name()).read_text()
    assert "@RAWEXT@" not in txt and "|cr3|" in txt and "|orf|" in txt


def test_legacy_history_is_read(tmp_path):
    (tmp_path / ".olympus_import_history.tsv").write_text("P1.JPG\t10\t2025-01-01\tx\n")
    assert core.load_history(tmp_path) == {("P1.JPG", 10): "2025-01-01"}


def test_cleanup_script_english(tmp_path):
    from dcim_import import i18n
    i18n.set_language("en")
    try:
        core.write_cleanup_script(tmp_path)
        txt = (tmp_path / "delete_RAW_without_JPG.bat").read_text()
        assert "Recycle Bin? (y/n)" in txt and "@" + "ASK@" not in txt
        assert i18n.tr("{n} Bilder · {m} markiert", n=3, m=1) == "3 images · 1 marked"
    finally:
        i18n.set_language("de")

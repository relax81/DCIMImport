"""Kernlogik: Karte finden, Dateien scannen, Import planen und ausführen.

Bewusst ohne Qt-Abhängigkeit, damit sich alles separat testen lässt.
"""
from __future__ import annotations

import hashlib
import re
import os
import shutil
import string
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterable

from .i18n import language, tr

JPG_EXT = {".jpg", ".jpeg"}
RAW_EXT = {
    ".orf", ".ori",                  # Olympus / OM System
    ".cr2", ".cr3", ".crw",          # Canon
    ".nef", ".nrw",                  # Nikon
    ".arw", ".srf", ".sr2",          # Sony
    ".raf",                          # Fujifilm
    ".rw2", ".rwl",                  # Panasonic, Leica
    ".pef",                          # Pentax
    ".srw",                          # Samsung
    ".x3f",                          # Sigma
    ".3fr", ".iiq", ".mos", ".erf", ".kdc", ".dcr", ".mrw",
    ".dng",                          # Adobe/Leica/Pentax/Handys
}
VIDEO_EXT = {".mov", ".mp4", ".avi", ".mts", ".m2ts", ".mkv", ".3gp", ".mxf"}

# DCF-Standard: DCIM\100XXXXX  (3 Ziffern + 5 Zeichen, Herstellerkürzel)
_DCF_DIR = re.compile(r"^[1-9]\d{2}[A-Za-z0-9_]{5}$")
VENDORS = {
    "OLYMP": "Olympus", "OMSYS": "OM System", "CANON": "Canon", "NIKON": "Nikon",
    "NCD": "Nikon", "MSDCF": "Sony", "_FUJI": "Fujifilm", "_PANA": "Panasonic",
    "PENTX": "Pentax", "RICOH": "Ricoh", "LEICA": "Leica", "SIGMA": "Sigma",
    "GOPRO": "GoPro", "MEDIA": "DJI", "APPLE": "iPhone", "ANDRO": "Android",
}

SUB_JPG = "jpg"
SUB_RAW = "raw"
SUB_VIDEO = "video"
_RENAMED = re.compile(r"^(.+)_\d+(\.[^.]+)$")


# ---------------------------------------------------------------- Karte finden

def candidate_roots() -> list[Path]:
    """Alle Laufwerks-Wurzeln (Windows) bzw. Mountpoints (zum Testen)."""
    if sys.platform == "win32":
        roots = []
        system = os.environ.get("SystemDrive", "C:").upper()[:1]
        for letter in string.ascii_uppercase[2:]:  # A/B auslassen
            if letter == system:  # Systemlaufwerk ist nie eine Speicherkarte
                continue
            p = Path(f"{letter}:\\")
            try:
                if p.exists():
                    roots.append(p)
            except OSError:
                pass
        return roots
    env = os.environ.get("DCIM_TEST_ROOTS")
    return [Path(p) for p in env.split(os.pathsep)] if env else []


def parse_only(text: str) -> list[str]:
    """'OLYMP, canon' -> ['OLYMP', 'CANON'] (leer = alle Kameras)."""
    return [t.strip().upper() for t in re.split(r"[,; ]+", text or "") if t.strip()]


def find_card_dirs(root: Path, only: list[str] | None = None) -> list[Path]:
    """Alle DCF-Bildordner (DCIM\\100XXXXX) einer Laufwerkswurzel, sortiert.

    `only`: nur Ordner, deren Herstellerkürzel einen dieser Texte enthält."""
    dcim = root / "DCIM"
    try:
        if not dcim.is_dir():
            return []
        dirs = [d for d in dcim.iterdir() if d.is_dir() and _DCF_DIR.match(d.name)]
    except OSError:
        return []
    if only:
        dirs = [d for d in dirs if any(o in d.name[3:].upper() for o in only)]
    return sorted(dirs, key=lambda d: d.name.upper())


def vendor_of(dir_name: str) -> str:
    tag = dir_name[3:].upper()
    for key, name in VENDORS.items():
        if key in tag:
            return name
    return tag


@dataclass
class Card:
    root: Path
    dirs: list[Path]

    @property
    def vendor(self) -> str:
        names = []
        for d in self.dirs:
            v = vendor_of(d.name)
            if v not in names:
                names.append(v)
        return " / ".join(names)

    @property
    def label(self) -> str:
        names = ", ".join(d.name for d in self.dirs)
        return f"{self.root}  {self.vendor}  ({names})"


def find_cards(only: list[str] | None = None) -> list[Card]:
    cards = []
    for r in candidate_roots():
        dirs = find_card_dirs(r, only)
        if dirs:
            cards.append(Card(r, dirs))
    return cards


# ---------------------------------------------------------------- Scan

@dataclass
class SrcFile:
    path: Path
    size: int
    mtime: float
    kind: str  # "jpg" | "raw" | "video" | "other"
    shot: datetime | None = None  # Aufnahmezeitpunkt

    @property
    def name(self) -> str:
        return self.path.name

    @property
    def stem(self) -> str:
        return self.path.stem.upper()


def kind_of(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in JPG_EXT:
        return "jpg"
    if ext in RAW_EXT:
        return "raw"
    if ext in VIDEO_EXT:
        return "video"
    return "other"


def exif_datetime(path: Path) -> datetime | None:
    """DateTimeOriginal aus einem JPG lesen (None, wenn nicht vorhanden)."""
    try:
        from PIL import Image
        with Image.open(path) as im:
            exif = im.getexif()
            raw = exif.get_ifd(0x8769).get(36867) or exif.get(306)
        if raw:
            return datetime.strptime(str(raw).strip("\x00 "), "%Y:%m:%d %H:%M:%S")
    except Exception:
        pass
    return None


def scan_card(card: Card, read_exif: bool,
              progress: Callable[[int, int], None] | None = None) -> list[SrcFile]:
    files: list[SrcFile] = []
    for d in card.dirs:
        for p in sorted(d.iterdir()):
            if p.is_file():
                st = p.stat()
                files.append(SrcFile(p, st.st_size, st.st_mtime, kind_of(p)))
    # Aufnahmedatum: JPG -> EXIF, RAW -> Datum des gleichnamigen JPG, sonst Dateidatum
    jpg_dates: dict[str, datetime] = {}
    jpgs = [f for f in files if f.kind == "jpg"]
    for i, f in enumerate(jpgs):
        if read_exif:
            f.shot = exif_datetime(f.path)
            if f.shot:
                jpg_dates[f.stem] = f.shot
        if progress:
            progress(i + 1, len(jpgs))
    for f in files:
        if f.shot is None:
            f.shot = jpg_dates.get(f.stem) or datetime.fromtimestamp(f.mtime)
    return files


# ---------------------------------------------------------------- Bereits importiert?

HISTORY_FILE = ".dcim_import_history.tsv"
LEGACY_HISTORY = (".olympus_import_history.tsv",)


def load_history(target_root: Path) -> dict[tuple[str, int], str]:
    """Import-Historie: merkt sich auch Dateien, die später aussortiert wurden."""
    out: dict[tuple[str, int], str] = {}
    for name in (HISTORY_FILE, *LEGACY_HISTORY):
        try:
            with open(target_root / name, encoding="utf-8") as fh:
                for line in fh:
                    parts = line.rstrip("\n").split("\t")
                    if len(parts) >= 3 and parts[1].isdigit():
                        out.setdefault((parts[0].upper(), int(parts[1])), parts[2])
        except OSError:
            pass
    return out


def append_history(target_root: Path, entries: list[tuple[str, int, str]]):
    if not entries:
        return
    path = target_root / HISTORY_FILE
    new = not path.exists()
    try:
        if not new and sys.platform == "win32":
            _set_hidden(path, False)  # versteckte Dateien lassen sich unter Windows nicht anhängen
        with open(path, "a", encoding="utf-8") as fh:
            stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
            for name, size, folder in entries:
                fh.write(f"{name.upper()}\t{size}\t{folder}\t{stamp}\n")
    except OSError:
        pass
    finally:
        if sys.platform == "win32":
            _set_hidden(path, True)


def _set_hidden(path: Path, hidden: bool):
    try:
        import ctypes
        attrs = ctypes.windll.kernel32.GetFileAttributesW(str(path))
        if attrs == -1 or attrs == 0xFFFFFFFF:
            return
        attrs = (attrs | 0x2) if hidden else (attrs & ~0x2)
        ctypes.windll.kernel32.SetFileAttributesW(str(path), attrs)
    except Exception:
        pass


def index_existing(target_root: Path, names: set[str]) -> dict[tuple[str, int], str]:
    """Sucht im Zielordner (rekursiv) nach Dateien mit gleichem Namen + Größe.

    Rückgabe: (NAME_UPPER, size) -> Name des obersten Unterordners, in dem sie liegt.
    Nur Dateien mit Namen aus `names` werden per stat() geprüft.
    """
    found: dict[tuple[str, int], str] = {}
    if not target_root.is_dir():
        return found
    names_u_hist = {n.upper() for n in names}
    found.update({k: v for k, v in load_history(target_root).items() if k[0] in names_u_hist})
    names_u = {n.upper() for n in names}
    for dirpath, dirnames, filenames in os.walk(target_root):
        dirnames[:] = [d for d in dirnames if d != "_geloescht"]
        for fn in filenames:
            # P1010001_1.JPG (umbenannt wegen Namensgleichheit) zählt wie P1010001.JPG
            base = _RENAMED.sub(r"\1\2", fn).upper()
            if base in names_u:
                p = Path(dirpath, fn)
                try:
                    size = p.stat().st_size
                except OSError:
                    continue
                rel = p.relative_to(target_root)
                top = rel.parts[0] if len(rel.parts) > 1 else "."
                found.setdefault((base, size), top)
    return found


# ---------------------------------------------------------------- Planung

@dataclass
class Options:
    target_root: Path
    suffix: str = ""
    by_shot_date: bool = False
    split: bool = True
    videos_separate: bool = True
    verify_hash: bool = False
    skip_already: bool = False
    cleanup_script: bool = True


@dataclass
class CopyJob:
    src: SrcFile
    dest: Path


@dataclass
class Plan:
    jobs: list[CopyJob]
    folders: list[Path]
    already: dict[str, int] = field(default_factory=dict)  # Ordner -> Anzahl
    skipped: int = 0  # wegen "schon importiert" weggelassen

    @property
    def total_bytes(self) -> int:
        return sum(j.src.size for j in self.jobs)


def folder_name(day: str, suffix: str) -> str:
    suffix = suffix.strip()
    bad = '<>:"/\\|?*'
    suffix = "".join(c for c in suffix if c not in bad).strip(" .")
    return f"{day} {suffix}" if suffix else day


def sub_for(kind: str, opt: Options) -> str:
    if kind == "video" and opt.videos_separate:
        return SUB_VIDEO
    if not opt.split:
        return ""
    return {"jpg": SUB_JPG, "raw": SUB_RAW}.get(kind, "")


def make_plan(files: Iterable[SrcFile], opt: Options,
              today: datetime | None = None) -> Plan:
    files = list(files)
    today = today or datetime.now()
    jobs: list[CopyJob] = []
    folders: list[Path] = []
    taken: set[str] = set()
    for f in files:
        day = (f.shot if opt.by_shot_date and f.shot else today).strftime("%Y-%m-%d")
        folder = opt.target_root / folder_name(day, opt.suffix)
        if folder not in folders:
            folders.append(folder)
        sub = sub_for(f.kind, opt)
        dest_dir = folder / sub if sub else folder
        dest = unique_dest(dest_dir / f.name, f.size, taken)
        taken.add(str(dest).upper())
        jobs.append(CopyJob(f, dest))

    existing = index_existing(opt.target_root, {f.name for f in files})
    already: dict[str, int] = {}
    keep: list[CopyJob] = []
    for j in jobs:
        hit = existing.get((j.src.name.upper(), j.src.size))
        if hit and (opt.target_root / hit) not in folders:
            already[hit] = already.get(hit, 0) + 1
            if opt.skip_already:
                continue
        keep.append(j)
    used = sorted(f for f in folders if any(j.dest.is_relative_to(f) for j in keep))
    return Plan(keep, used, already, skipped=len(jobs) - len(keep))


def unique_dest(dest: Path, size: int, taken: set[str]) -> Path:
    """Gleicher Name schon da? Gleiche Größe = dieselbe Datei (wird überschrieben),
    sonst P1010001_1.JPG usw. (z. B. wenn 101xxxxx und 102xxxxx gleiche Namen haben)."""
    cand = dest
    n = 1
    while True:
        key = str(cand).upper()
        if key not in taken:
            if not cand.exists():
                return cand
            try:
                if cand.stat().st_size == size:
                    return cand
            except OSError:
                pass
        cand = dest.with_name(f"{dest.stem}_{n}{dest.suffix}")
        n += 1


# ---------------------------------------------------------------- Ausführen

class Cancelled(Exception):
    pass


def file_hash(path: Path, chunk: int = 4 << 20) -> str:
    h = hashlib.blake2b(digest_size=16)
    with open(path, "rb") as fh:
        while b := fh.read(chunk):
            h.update(b)
    return h.hexdigest()


@dataclass
class Result:
    copied: int = 0
    skipped_same: int = 0
    errors: list[str] = field(default_factory=list)
    verified: bool = False


def run_plan(plan: Plan, opt: Options,
             on_progress: Callable[[int, int, str], None] | None = None,
             is_cancelled: Callable[[], bool] = lambda: False) -> Result:
    res = Result()
    ok_entries: list[tuple[str, int, str]] = []
    total = plan.total_bytes or 1
    done = 0
    for j in plan.jobs:
        if is_cancelled():
            raise Cancelled()
        try:
            j.dest.parent.mkdir(parents=True, exist_ok=True)
            if j.dest.exists() and j.dest.stat().st_size == j.src.size and not opt.verify_hash:
                res.skipped_same += 1
            else:
                shutil.copy2(j.src.path, j.dest)
                if j.dest.stat().st_size != j.src.size:
                    raise IOError(tr("Größe stimmt nach dem Kopieren nicht"))
                res.copied += 1
            if opt.verify_hash and file_hash(j.src.path) != file_hash(j.dest):
                raise IOError(tr("Prüfsumme stimmt nicht"))
        except Cancelled:
            raise
        except Exception as e:  # weiter mit der nächsten Datei
            res.errors.append(f"{j.src.path}: {e}")
        else:
            try:
                top = j.dest.relative_to(opt.target_root).parts[0]
                ok_entries.append((j.src.name, j.src.size, top))
            except ValueError:
                pass
        done += j.src.size
        if on_progress:
            on_progress(done, total, j.src.name)
    append_history(opt.target_root, ok_entries)
    if opt.cleanup_script:
        for folder in plan.folders:
            write_cleanup_script(folder)
    res.verified = not res.errors
    return res


# ---------------------------------------------------------------- Karte auswerfen

def eject(root: Path) -> bool:
    if sys.platform != "win32":
        return False
    drive = str(root)[:2]
    ps = ("$d=(New-Object -ComObject Shell.Application).Namespace(17).ParseName('%s');"
          "if($d){$d.InvokeVerb('Eject')}" % drive)
    import time
    for attempt in range(3):
        try:
            subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                           timeout=15, creationflags=0x08000000)  # CREATE_NO_WINDOW
        except Exception:
            return False
        # Explorer wirft asynchron aus -> bis zu 5 s warten
        for _ in range(25):
            if not Path(f"{drive}\\DCIM").exists():
                return True
            time.sleep(0.2)
    return False


# ---------------------------------------------------------------- Aussortieren

def pairs_in(folder: Path) -> list[tuple[Path, list[Path]]]:
    """JPGs eines Importordners mit den zugehörigen RAWs (gleicher Name)."""
    jdir = folder / SUB_JPG if (folder / SUB_JPG).is_dir() else folder
    rdir = folder / SUB_RAW if (folder / SUB_RAW).is_dir() else folder
    raws: dict[str, list[Path]] = {}
    if rdir.is_dir():
        for p in rdir.iterdir():
            if p.is_file() and kind_of(p) == "raw":
                raws.setdefault(p.stem.upper(), []).append(p)
    out = []
    if jdir.is_dir():
        for p in sorted(jdir.iterdir(), key=lambda x: x.name.upper()):
            if p.is_file() and kind_of(p) == "jpg":
                out.append((p, raws.get(p.stem.upper(), [])))
    return out


def orphan_raws(folder: Path) -> list[Path]:
    jdir = folder / SUB_JPG if (folder / SUB_JPG).is_dir() else folder
    rdir = folder / SUB_RAW if (folder / SUB_RAW).is_dir() else folder
    if not rdir.is_dir():
        return []
    jpg_stems = set()
    if jdir.is_dir():
        jpg_stems = {p.stem.upper() for p in jdir.iterdir() if kind_of(p) == "jpg"}
    return sorted(p for p in rdir.iterdir()
                  if p.is_file() and kind_of(p) == "raw" and p.stem.upper() not in jpg_stems)


def to_trash(paths: Iterable[Path]) -> list[str]:
    from send2trash import send2trash
    errors = []
    for p in paths:
        try:
            send2trash(str(p))
        except Exception as e:
            errors.append(f"{p}: {e}")
    return errors


CLEANUP_NAMES = {"de": "RAW_ohne_JPG_loeschen.bat", "en": "delete_RAW_without_JPG.bat"}
CLEANUP_NAME = CLEANUP_NAMES["de"]


def cleanup_name() -> str:
    return CLEANUP_NAMES.get(language(), CLEANUP_NAMES["en"])


# Texte im Script (nur ASCII, die Konsole nutzt eine alte Codepage)
_CLEANUP_TEXT = {
    "de": {
        "REM": "RAW-Dateien loeschen, deren JPG schon aussortiert wurde (-> Papierkorb).",
        "NOJPG": "Keine JPGs gefunden - abgebrochen, damit nicht alle RAWs geloescht werden.",
        "NONE": "Keine RAW-Dateien ohne JPG.",
        "ASK": "{0} RAW-Dateien ohne JPG in den Papierkorb verschieben? (j/n)",
        "KEPT": "Nichts geloescht.",
        "DONE": "{0} Dateien im Papierkorb.",
    },
    "en": {
        "REM": "Delete RAW files whose JPG has already been culled (-> Recycle Bin).",
        "NOJPG": "No JPGs found - aborted so that not all RAWs get deleted.",
        "NONE": "No RAW files without JPG.",
        "ASK": "Move {0} RAW files without JPG to the Recycle Bin? (y/n)",
        "KEPT": "Nothing deleted.",
        "DONE": "{0} files moved to the Recycle Bin.",
    },
}

# Batch-Huelle + PowerShell-Teil in einer Datei (nur ASCII, damit Codepage egal ist).
# Verschiebt RAWs ohne passendes JPG in den Papierkorb, nach Rueckfrage.
CLEANUP_SCRIPT = r"""@echo off
rem @REM@
set "OI_DIR=%~dp0"
set "OI_SELF=%~f0"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$p = ((Get-Content -LiteralPath $env:OI_SELF -Raw) -split ('#'+'PS'+'#'))[1]; & ([scriptblock]::Create($p))"
pause
exit /b
#PS#
Add-Type -AssemblyName Microsoft.VisualBasic
$d = $env:OI_DIR.TrimEnd('\')
$jd = if (Test-Path -LiteralPath "$d\jpg") { "$d\jpg" } else { $d }
$rd = if (Test-Path -LiteralPath "$d\raw") { "$d\raw" } else { $d }
$jpg = @{}
Get-ChildItem -LiteralPath $jd -File | Where-Object { $_.Extension -match '^\.jpe?g$' } |
    ForEach-Object { $jpg[$_.BaseName.ToUpper()] = 1 }
if ($jpg.Count -eq 0) { Write-Host '@NOJPG@'; return }
$orph = @(Get-ChildItem -LiteralPath $rd -File | Where-Object {
    $_.Extension -match '^\.(@RAWEXT@)$' -and -not $jpg.ContainsKey($_.BaseName.ToUpper()) })
if ($orph.Count -eq 0) { Write-Host '@NONE@'; return }
$orph | ForEach-Object { Write-Host ('  ' + $_.Name) }
Write-Host ''
$a = Read-Host ("@ASK@" -f $orph.Count)
if ($a -notmatch '^[jJyY]') { Write-Host '@KEPT@'; return }
foreach ($f in $orph) {
    [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile($f.FullName, 'OnlyErrorDialogs', 'SendToRecycleBin')
}
Write-Host ("@DONE@" -f $orph.Count)
"""


def write_cleanup_script(folder: Path):
    if not folder.is_dir():
        return
    try:
        exts = "|".join(sorted(e.lstrip(".") for e in RAW_EXT))
        data = CLEANUP_SCRIPT.replace("@RAWEXT@", exts)
        for key, text in _CLEANUP_TEXT.get(language(), _CLEANUP_TEXT["en"]).items():
            data = data.replace(f"@{key}@", text)
        data = data.lstrip("\n").replace("\r\n", "\n").replace("\n", "\r\n")
        (folder / cleanup_name()).write_bytes(data.encode("ascii"))
    except OSError:
        pass


def human_size(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{int(n)} B"
        n /= 1024
    return f"{n:.1f} GB"

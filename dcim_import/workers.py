"""Hintergrund-Threads für Scan und Import, damit die GUI nicht hängt."""
from __future__ import annotations

from collections import Counter
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from . import core
from .i18n import tr


class ScanWorker(QThread):
    """Schneller Vorab-Scan: was ist auf der Karte, was gab es schon?"""
    done = Signal(object)  # dict mit Zusammenfassung
    failed = Signal(str)

    def __init__(self, card: core.Card, opt: core.Options):
        super().__init__()
        self.card, self.opt = card, opt

    def run(self):
        try:
            files = core.scan_card(self.card, read_exif=self.opt.by_shot_date)
            plan = core.make_plan(files, self.opt)
            kinds = Counter(f.kind for f in files)
            shots = [f.shot for f in files if f.shot]
            self.done.emit({
                "count": len(files),
                "kinds": kinds,
                "bytes": plan.total_bytes,
                "first": min(shots) if shots else None,
                "last": max(shots) if shots else None,
                "folders": plan.folders,
                "already": plan.already,
            })
        except Exception as e:
            self.failed.emit(str(e))


class ImportWorker(QThread):
    log = Signal(str)
    progress = Signal(int, int)  # Promille, 1000
    status = Signal(str)
    finished_ok = Signal(object)  # (Result, folders)
    failed = Signal(str)

    def __init__(self, card: core.Card, opt: core.Options, eject: bool):
        super().__init__()
        self.card, self.opt, self.eject = card, opt, eject
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        try:
            self.status.emit(tr("Lese Karte …"))
            files = core.scan_card(
                self.card, read_exif=self.opt.by_shot_date,
                progress=lambda i, n: self.status.emit(tr("Lese Aufnahmedaten {i}/{n} …", i=i, n=n)))
            if not files:
                self.failed.emit(tr("Keine Dateien auf der Karte gefunden."))
                return
            plan = core.make_plan(files, self.opt)
            for name, n in sorted(plan.already.items()):
                msg = ("{n} Datei(en) schon importiert in „{name}“ – übersprungen."
                       if self.opt.skip_already else
                       "{n} Datei(en) schon importiert in „{name}“ – werden trotzdem kopiert.")
                self.log.emit(tr(msg, n=n, name=name))
            if not plan.jobs:
                self.log.emit(tr("Nichts Neues zu kopieren."))
            self.log.emit(tr("Kopiere {n} Dateien ({size}) nach:", n=len(plan.jobs),
                             size=core.human_size(plan.total_bytes)))
            for f in plan.folders:
                self.log.emit(f"   {f}")

            def prog(done, total, name):
                self.progress.emit(int(done * 1000 / total), 1000)
                self.status.emit(f"{name}  ·  {core.human_size(done)} / "
                                 f"{core.human_size(total)}")

            res = core.run_plan(plan, self.opt, prog, lambda: self._cancel)
            for e in res.errors:
                self.log.emit(tr("FEHLER: {e}", e=e))
            if res.skipped_same:
                self.log.emit(tr("{n} Datei(en) lagen schon identisch im Zielordner und "
                                 "wurden übersprungen.", n=res.skipped_same))
            if self.eject and res.verified:
                self.status.emit(tr("Werfe Karte aus …"))
                ok = core.eject(self.card.root)
                self.log.emit(tr("Karte ausgeworfen.") if ok else
                              tr("Karte konnte nicht ausgeworfen werden (noch in Benutzung?)."))
            self.finished_ok.emit((res, plan.folders))
        except core.Cancelled:
            self.failed.emit(tr("Abgebrochen. Bereits kopierte Dateien bleiben liegen."))
        except Exception as e:
            self.failed.emit(tr("Unerwarteter Fehler: {e}", e=e))


class ThumbWorker(QThread):
    """Lädt Vorschaubilder nacheinander (JPEG wird beim Lesen herunterskaliert)."""
    thumb = Signal(int, object)  # Index, QImage

    def __init__(self, paths: list[Path], size: int):
        super().__init__()
        self.paths, self.size = paths, size
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        for i, p in enumerate(self.paths):
            if self._stop:
                return
            self.thumb.emit(i, load_scaled(p, self.size))


def load_scaled(path: Path, box: int):
    """Bild passend in ein Quadrat `box` laden, EXIF-Drehung berücksichtigt.

    Der JPEG-Decoder liest dabei direkt in reduzierter Auflösung (schnell)."""
    from PySide6.QtCore import QSize, Qt
    from PySide6.QtGui import QImageReader
    r = QImageReader(str(path))
    r.setAutoTransform(True)
    s = r.size()
    if s.isValid() and (s.width() > 2 * box or s.height() > 2 * box):
        # doppelte Zielgröße lesen, dann glatt herunterskalieren (bessere Qualität)
        r.setScaledSize(s.scaled(QSize(2 * box, 2 * box), Qt.KeepAspectRatio))
    img = r.read()
    if not img.isNull():
        img = img.scaled(box, box, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    return img

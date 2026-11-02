"""Tab „Importieren“."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QTimer, Signal
from PySide6.QtGui import QKeySequence, QPalette, QShortcut
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QPlainTextEdit, QProgressBar, QPushButton, QSizePolicy,
    QVBoxLayout, QWidget,
)

from . import core
from .i18n import date_fmt, tr
from .workers import ImportWorker, ScanWorker

DEFAULT_TARGET = str(Path.home() / "Desktop" / "import")


def muted(label: QLabel):
    """Dezente Schrift, die im hellen und dunklen Modus lesbar bleibt."""
    pal = label.palette()
    pal.setColor(QPalette.WindowText, pal.color(QPalette.PlaceholderText))
    label.setPalette(pal)


class ImportTab(QWidget):
    imported = Signal(object)      # Liste der Zielordner
    cards_changed = Signal(list)   # aktuelle Karten (für Tray-Erkennung)

    def __init__(self, settings: QSettings):
        super().__init__()
        self.s = settings
        self.cards: list[core.Card] = []
        self.worker: ImportWorker | None = None
        self.scanner: ScanWorker | None = None
        self._scan_pending = False

        # ---------- Karte
        self.card_combo = QComboBox()
        self.card_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.card_status = QLabel(tr("Suche Karte …"))
        self.card_status.setWordWrap(True)
        self.card_status.setTextFormat(Qt.RichText)
        btn_rescan = QPushButton(tr("Neu suchen  [F5]"))
        btn_rescan.clicked.connect(lambda: self.poll_cards(force=True))
        row = QHBoxLayout()
        row.addWidget(self.card_combo, 1)
        row.addWidget(btn_rescan)
        g_card = QGroupBox(tr("SD-Karte"))
        v = QVBoxLayout(g_card)
        v.addLayout(row)
        v.addWidget(self.card_status)
        self.o_skip = QCheckBox()
        self.o_skip.setChecked(self.s.value("skip_already", True, type=bool))
        self.o_skip.toggled.connect(lambda val: (self.s.setValue("skip_already", val),
                                                 self._update_start_text()))
        self.o_skip.setVisible(False)
        v.addWidget(self.o_skip)
        self._summary: dict | None = None

        # ---------- Ziel
        self.target = QLineEdit(self.s.value("target", DEFAULT_TARGET))
        btn_browse = QPushButton("…")
        btn_browse.setFixedWidth(32)
        btn_browse.clicked.connect(self.browse_target)
        trow = QHBoxLayout()
        trow.addWidget(self.target, 1)
        trow.addWidget(btn_browse)
        self.suffix = QLineEdit()
        self.suffix.setPlaceholderText(tr("optional, z. B. Headphone Stand"))
        self.dest_preview = QLabel()
        muted(self.dest_preview)
        self.dest_preview.setWordWrap(True)
        g_target = QGroupBox(tr("Ziel"))
        f = QFormLayout(g_target)
        f.addRow(tr("Hauptordner"), trow)
        f.addRow(tr("Ordner-Zusatz"), self.suffix)
        f.addRow("", self.dest_preview)

        # ---------- Optionen
        def cb(text, key, default):
            c = QCheckBox(tr(text))
            c.setChecked(self.s.value(key, default, type=bool))
            c.toggled.connect(lambda val: self.s.setValue(key, val))
            return c

        self.o_split = cb("JPG und RAW in Unterordner aufteilen", "split", True)
        self.o_video = cb("Videos in eigenen Ordner", "videos", True)
        self.o_bydate = cb("Ordner nach Aufnahmedatum statt Importdatum", "by_date", False)
        self.o_verify = cb("Kopie per Prüfsumme kontrollieren (langsamer)", "verify", False)
        self.o_eject = cb("Karte danach auswerfen", "eject", False)
        self.o_gallery = cb("Danach zum Aussortieren wechseln", "to_gallery", True)
        self.o_cleanup = cb("Aufräum-Script (RAW ohne JPG) in den Ordner legen",
                            "cleanup_script", True)
        self.o_cleanup.setToolTip(
            tr("Legt {name} in jeden Importordner.\n"
               "Praktisch, wenn du JPGs später mit einem anderen Programm aussortierst:\n"
               "Doppelklick verschiebt die übrig gebliebenen RAWs in den Papierkorb.",
               name=core.cleanup_name()))
        g_opt = QGroupBox(tr("Optionen"))
        ov = QVBoxLayout(g_opt)
        for w in (self.o_split, self.o_video, self.o_bydate, self.o_verify,
                  self.o_eject, self.o_gallery, self.o_cleanup):
            ov.addWidget(w)

        # ---------- Start / Fortschritt
        self.btn_start = QPushButton(tr("Importieren   [Strg+Enter]"))
        self.btn_start.setMinimumHeight(44)
        self.btn_start.setStyleSheet("font-size: 15px; font-weight: 600;")
        self.btn_start.clicked.connect(self.start)
        self.btn_cancel = QPushButton(tr("Abbrechen   [Esc]"))
        self.btn_cancel.setMinimumHeight(44)
        self.btn_cancel.setVisible(False)
        self.btn_cancel.clicked.connect(self.cancel)
        brow = QHBoxLayout()
        brow.addWidget(self.btn_start, 1)
        brow.addWidget(self.btn_cancel)
        self.bar = QProgressBar()
        self.bar.setRange(0, 1000)
        self.bar.setTextVisible(False)
        self.status = QLabel("")
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(2000)

        root = QVBoxLayout(self)
        top = QHBoxLayout()
        left = QVBoxLayout()
        left.addWidget(g_card)
        left.addWidget(g_target)
        left.addStretch(1)
        top.addLayout(left, 3)
        top.addWidget(g_opt, 2)
        root.addLayout(top)
        root.addLayout(brow)
        root.addWidget(self.bar)
        root.addWidget(self.status)
        root.addWidget(self.log, 1)

        # ---------- Verdrahtung
        for w in (self.target, self.suffix):
            w.textChanged.connect(self.options_changed)
        for c in (self.o_split, self.o_video, self.o_bydate):
            c.toggled.connect(self.options_changed)
        self.card_combo.currentIndexChanged.connect(lambda _: self.request_scan())

        for key in ("Ctrl+Return", "Ctrl+Enter"):
            QShortcut(QKeySequence(key), self, activated=self.start)
        QShortcut(QKeySequence(Qt.Key_Escape), self, activated=self.cancel)
        QShortcut(QKeySequence(Qt.Key_F5), self, activated=lambda: self.poll_cards(force=True))

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.poll_cards)
        self.timer.start(2000)
        QTimer.singleShot(0, lambda: self.poll_cards(force=True))
        self.update_preview()

    # ------------------------------------------------------------ Optionen

    def options(self) -> core.Options:
        return core.Options(
            target_root=Path(self.target.text().strip() or DEFAULT_TARGET),
            suffix=self.suffix.text(),
            by_shot_date=self.o_bydate.isChecked(),
            split=self.o_split.isChecked(),
            videos_separate=self.o_video.isChecked(),
            verify_hash=self.o_verify.isChecked(),
            skip_already=self.o_skip.isChecked() and not self.o_skip.isHidden(),
            cleanup_script=self.o_cleanup.isChecked(),
        )

    def browse_target(self):
        d = QFileDialog.getExistingDirectory(self, tr("Hauptordner wählen"), self.target.text())
        if d:
            self.target.setText(str(Path(d)))

    def options_changed(self):
        self.s.setValue("target", self.target.text().strip())
        self.update_preview()
        self.request_scan(delay=600)

    def update_preview(self):
        opt = self.options()
        if opt.by_shot_date:
            name = core.folder_name(tr("JJJJ-MM-TT"), opt.suffix) + tr("  (je Aufnahmetag)")
        else:
            name = core.folder_name(datetime.now().strftime("%Y-%m-%d"), opt.suffix)
        self.dest_preview.setText(f"→ {opt.target_root / name}")

    # ------------------------------------------------------------ Karte

    def current_card(self) -> core.Card | None:
        i = self.card_combo.currentIndex()
        return self.cards[i] if 0 <= i < len(self.cards) else None

    def poll_cards(self, force: bool = False):
        if self.worker and self.worker.isRunning():
            return
        cards = core.find_cards(core.parse_only(self.s.value("only", "")))
        if not force and [c.label for c in cards] == [c.label for c in self.cards]:
            return
        prev = self.current_card()
        self.cards = cards
        self.card_combo.blockSignals(True)
        self.card_combo.clear()
        for c in cards:
            self.card_combo.addItem(c.label)
        if prev:
            for i, c in enumerate(cards):
                if c.root == prev.root:
                    self.card_combo.setCurrentIndex(i)
        self.card_combo.blockSignals(False)
        self.card_combo.setEnabled(len(cards) > 1)
        self.cards_changed.emit(cards)
        if not cards:
            self.o_skip.setVisible(False)
            self._summary = None
            only = self.s.value("only", "")
            extra = tr(" (Filter: {only})", only=only) if only else ""
            self.card_status.setText(tr("Keine Kamerakarte gefunden{extra}. "
                                        "Einstecken – wird automatisch erkannt.", extra=extra))
            self.btn_start.setEnabled(False)
        else:
            self.request_scan()

    def request_scan(self, delay: int = 0):
        card = self.current_card()
        if not card:
            return
        self.card_status.setText(tr("Prüfe Karteninhalt …"))
        self._scan_pending = True
        QTimer.singleShot(delay, self._do_scan)

    def _do_scan(self):
        if not self._scan_pending:
            return
        if self.scanner and self.scanner.isRunning():
            QTimer.singleShot(300, self._do_scan)
            return
        self._scan_pending = False
        card = self.current_card()
        if not card:
            return
        opt = self.options()
        opt.skip_already = False
        self.scanner = ScanWorker(card, opt)
        self.scanner.done.connect(self.show_summary)
        self.scanner.failed.connect(lambda e: self.card_status.setText(tr("Fehler: {e}", e=e)))
        self.scanner.start()

    def show_summary(self, s: dict):
        self._summary = s
        if s["count"] == 0:
            self.card_status.setText(tr("Karte ist leer."))
            self.o_skip.setVisible(False)
            self.btn_start.setEnabled(False)
            return
        k = s["kinds"]
        parts = [f"<b>{k.get('jpg', 0)}</b> JPG", f"<b>{k.get('raw', 0)}</b> RAW"]
        if k.get("video"):
            parts.append(f"<b>{k['video']}</b> Video")
        if k.get("other"):
            parts.append(tr("{n} sonstige", n=k['other']))
        txt = " · ".join(parts) + f" · {core.human_size(s['bytes'])}"
        if s["first"]:
            a, b = s["first"].strftime(date_fmt()), s["last"].strftime(date_fmt())
            txt += "<br>" + tr("Aufnahmen vom {a}", a=a) + (tr(" bis {b}", b=b) if a != b else "")
        if len(s["folders"]) > 1:
            txt += "<br>→ " + tr("{n} Ordner", n=len(s['folders']))
        n_already = sum(s["already"].values())
        if n_already:
            items = ", ".join(tr("{n}× in „{name}“", n=n, name=name) for name, n in
                              sorted(s["already"].items()))
            txt += ("<br><span style='color:#e09000'>"
                    + tr("Schon importiert: {items}", items=items) + "</span>")
            self.o_skip.setText(tr("Schon importierte überspringen ({n} Dateien)", n=n_already))
        self.o_skip.setVisible(bool(n_already))
        self.card_status.setText(txt)
        self.btn_start.setEnabled(True)
        self._update_start_text()

    def _update_start_text(self):
        s = self._summary
        if not s or not s["count"]:
            self.btn_start.setText(tr("Importieren   [Strg+Enter]"))
            return
        n = s["count"]
        if not self.o_skip.isHidden() and self.o_skip.isChecked():
            n -= sum(s["already"].values())
        self.btn_start.setText(tr("{n} Dateien importieren   [Strg+Enter]", n=n) if n
                               else tr("Nichts Neues zu importieren"))
        self.btn_start.setEnabled(n > 0)

    # ------------------------------------------------------------ Import

    def start(self):
        card = self.current_card()
        if (not card or not self.btn_start.isEnabled() or self.btn_start.isHidden()
                or (self.worker and self.worker.isRunning())):
            return
        opt = self.options()
        self.log.clear()
        self.status.setStyleSheet("")
        self.bar.setValue(0)
        self.set_running(True)
        self.worker = ImportWorker(card, opt, self.o_eject.isChecked())
        self.worker.log.connect(self.log.appendPlainText)
        self.worker.status.connect(self.status.setText)
        self.worker.progress.connect(lambda v, _: self.bar.setValue(v))
        self.worker.finished_ok.connect(self.on_done)
        self.worker.failed.connect(self.on_failed)
        self.worker.start()

    def cancel(self):
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.status.setText(tr("Breche ab …"))

    def set_running(self, running: bool):
        self.btn_start.setVisible(not running)
        self.btn_cancel.setVisible(running)
        for w in (self.target, self.suffix, self.card_combo):
            w.setEnabled(not running)

    def on_done(self, payload):
        res, folders = payload
        self.set_running(False)
        self.bar.setValue(1000)
        if res.errors:
            self.status.setText(tr("Fertig mit {n} Fehler(n) – Karte NICHT "
                                   "formatieren, Log prüfen.", n=len(res.errors)))
            self.status.setStyleSheet("color: #c62828; font-weight: 600;")
        else:
            check = tr("per Prüfsumme") if self.options().verify_hash else tr("per Dateigröße")
            self.status.setText(tr("✔ {n} Dateien kopiert, {check} geprüft – "
                                   "Karte kann formatiert werden.", n=res.copied, check=check))
            self.status.setStyleSheet("color: #2e7d32; font-weight: 600;")
        self.log.appendPlainText(tr("Fertig."))
        self.poll_cards(force=True)
        if self.o_gallery.isChecked() and folders:
            self.imported.emit(folders)

    def on_failed(self, msg: str):
        self.set_running(False)
        self.status.setText(msg)
        self.status.setStyleSheet("color: #c62828; font-weight: 600;")
        self.log.appendPlainText(msg)

    def shutdown(self):
        """Laufende Threads beenden, bevor das Programm schließt."""
        self.timer.stop()
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.worker.wait(5000)
        if self.scanner and self.scanner.isRunning():
            self.scanner.wait(10000)

    def busy(self) -> bool:
        return bool(self.worker and self.worker.isRunning())

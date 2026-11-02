"""Hauptfenster, Infobereich (Tray), Autostart, Einzelinstanz."""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QLibraryInfo, QPointF, QProcess, QSettings, Qt, QTranslator
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QMainWindow, QMenu, QMessageBox, QSystemTrayIcon,
    QTabWidget, QVBoxLayout, QWidget,
)

from . import __version__
from .gallery_tab import GalleryTab
from .i18n import LANGS, language, set_language, system_language, tr
from .import_tab import ImportTab

APP_NAME = "DCIM Import"
APP_ID = "LeifDCIMImport"
LEGACY_APP_IDS = ("LeifOlympusImport",)
REPO_URL = "https://github.com/relax81/DCIMImport"
_SERVER = None  # QLocalServer der laufenden Instanz


def set_language_preview(code: str) -> str:
    """Welche Sprache würde die Auswahl ergeben (ohne sie zu aktivieren)?"""
    return system_language() if code in ("", "auto", None) else code


RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def app_icon() -> QIcon:
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        pm = QPixmap(size, size)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QColor("#1f3b5c"))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(0, 0, size, size, size * 0.22, size * 0.22)
        # Kamera-Objektiv
        p.setBrush(QColor("#e8eef5"))
        r = size * 0.30
        p.drawEllipse(size / 2 - r, size / 2 - r * 0.85, 2 * r, 2 * r)
        p.setBrush(QColor("#1f3b5c"))
        r2 = r * 0.55
        p.drawEllipse(size / 2 - r2, size / 2 - r * 0.85 + (r - r2), 2 * r2, 2 * r2)
        # Pfeil nach unten (Import)
        p.setBrush(QColor("#f2a900"))
        w = size * 0.18
        y = size * 0.80
        p.drawPolygon([
            QPointF(size / 2 - w, y - w * 0.6),
            QPointF(size / 2 + w, y - w * 0.6),
            QPointF(size / 2, y + w * 0.5),
        ])
        p.end()
        icon.addPixmap(pm)
    return icon


# ---------------------------------------------------------------- Autostart (Windows)

def autostart_command() -> str:
    if getattr(sys, "frozen", False):  # PyInstaller-.exe
        return f'"{sys.executable}" --tray'
    pyw = Path(sys.executable).with_name("pythonw.exe")
    exe = pyw if pyw.exists() else Path(sys.executable)
    main = Path(sys.argv[0]).resolve()
    return f'"{exe}" "{main}" --tray'


def autostart_enabled() -> bool:
    if sys.platform != "win32":
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            winreg.QueryValueEx(k, APP_ID)
            return True
    except OSError:
        return False


def set_autostart(on: bool) -> bool:
    if sys.platform != "win32":
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
            if on:
                winreg.SetValueEx(k, APP_ID, 0, winreg.REG_SZ, autostart_command())
            else:
                try:
                    winreg.DeleteValue(k, APP_ID)
                except FileNotFoundError:
                    pass
        return True
    except OSError:
        return False


def migrate_legacy(settings: QSettings):
    """Einstellungen + Autostart der früheren „Olympus Import“-Version übernehmen."""
    if settings.value("migrated", False, type=bool):
        return
    old = QSettings("Leif", "OlympusImport")
    for key in old.allKeys():
        if not settings.contains(key):
            settings.setValue(key, old.value(key))
    settings.setValue("migrated", True)
    if sys.platform == "win32":
        import winreg
        had_old = False
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0,
                                winreg.KEY_QUERY_VALUE | winreg.KEY_SET_VALUE) as k:
                for legacy in LEGACY_APP_IDS:
                    try:
                        winreg.QueryValueEx(k, legacy)
                        winreg.DeleteValue(k, legacy)
                        had_old = True
                    except OSError:
                        pass
        except OSError:
            pass
        if had_old:
            set_autostart(True)  # auf das neue Programm umbiegen


# ---------------------------------------------------------------- Einstellungen-Tab

class SettingsTab(QWidget):
    def __init__(self, settings: QSettings, win: "MainWindow"):
        super().__init__()
        self.s, self.win = settings, win
        self.c_tray = QCheckBox(tr("Im Infobereich weiterlaufen, wenn das Fenster geschlossen wird"))
        self.c_tray.setChecked(self.s.value("tray", False, type=bool))
        self.c_popup = QCheckBox(tr("Fenster automatisch öffnen, wenn eine Karte eingesteckt wird"))
        self.c_popup.setChecked(self.s.value("popup", True, type=bool))
        self.c_auto = QCheckBox(tr("Mit Windows starten (unsichtbar im Infobereich)"))
        self.c_auto.setChecked(autostart_enabled())
        self.c_auto.setEnabled(sys.platform == "win32")

        self.c_tray.toggled.connect(self._tray)
        self.c_popup.toggled.connect(lambda v: self.s.setValue("popup", v))
        self.c_auto.toggled.connect(self._auto)

        lay = QVBoxLayout(self)

        # ---------- Sprache
        lay.addWidget(QLabel(tr("<b>Sprache</b>")))
        lang_row = QHBoxLayout()
        lang_row.addWidget(QLabel(tr("Sprache:")))
        self.cb_lang = QComboBox()
        for code, name in LANGS.items():
            self.cb_lang.addItem(name, code)
        self.cb_lang.setCurrentIndex(max(0, self.cb_lang.findData(self.s.value("lang", "auto"))))
        self.cb_lang.currentIndexChanged.connect(self._lang)
        lang_row.addWidget(self.cb_lang)
        self.lang_note = QLabel(tr("Wird nach einem Neustart übernommen."))
        self.btn_restart = QPushButton(tr("Jetzt neu starten"))
        self.btn_restart.clicked.connect(self.win.restart)
        for w in (self.lang_note, self.btn_restart):
            w.setVisible(False)
            lang_row.addWidget(w)
        lang_row.addStretch(1)
        lay.addLayout(lang_row)
        lay.addSpacing(16)

        lay.addWidget(QLabel(tr("<b>Autostart / Hintergrund</b>")))
        lay.addWidget(self.c_tray)
        lay.addWidget(self.c_popup)
        lay.addWidget(self.c_auto)
        note = QLabel(tr("„Mit Windows starten“ schaltet den Infobereich automatisch mit ein. "
                         "Beenden dann über Rechtsklick aufs Symbol → Beenden."))
        note.setWordWrap(True)
        pal = note.palette()
        pal.setColor(note.foregroundRole(), pal.color(pal.ColorRole.PlaceholderText))
        note.setPalette(pal)
        lay.addWidget(note)

        lay.addSpacing(16)
        lay.addWidget(QLabel(tr("<b>Kameras</b>")))
        only_row = QHBoxLayout()
        only_row.addWidget(QLabel(tr("Nur diese Kameras:")))
        self.e_only = QLineEdit(self.s.value("only", ""))
        self.e_only.setPlaceholderText(tr("leer = alle, z. B. OLYMP oder CANON, NIKON"))
        self.e_only.textChanged.connect(self._only)
        only_row.addWidget(self.e_only, 1)
        lay.addLayout(only_row)
        hint = QLabel(tr("Vergleicht mit dem Herstellerkürzel im Kartenordner "
                         "(DCIM\\100<b>OLYMP</b>, 100<b>CANON</b>, 100<b>MSDCF</b> = Sony, "
                         "100<b>_FUJI</b> …). "
                         "So werden z. B. Drohnen- oder Actioncam-Karten ignoriert."))
        hint.setWordWrap(True)
        hint.setPalette(pal)
        lay.addWidget(hint)

        lay.addStretch(1)
        lgpl = "<a href='https://www.gnu.org/licenses/lgpl-3.0.html'>LGPL v3</a>"
        qtsrc = f"<a href='https://code.qt.io/'>{tr('Qt-Quellcode')}</a>"
        about = QLabel(
            f"<b>{APP_NAME} {__version__}</b> · {tr('MIT-Lizenz')} · "
            f"<a href='{REPO_URL}'>{tr('Quellcode')}</a><br>"
            + tr("Verwendet Qt for Python (PySide6, {lgpl}, {qtsrc}), Pillow (MIT-CMU) und "
                 "Send2Trash (BSD-3). Details in THIRD_PARTY_LICENSES.md im Repository.",
                 lgpl=lgpl, qtsrc=qtsrc))
        about.setWordWrap(True)
        about.setOpenExternalLinks(True)
        about.setTextFormat(Qt.RichText)
        lay.addWidget(about)

    def _lang(self, _i: int):
        code = self.cb_lang.currentData()
        self.s.setValue("lang", code)
        changed = set_language_preview(code) != language()
        self.lang_note.setVisible(changed)
        self.btn_restart.setVisible(changed)

    def _only(self, text: str):
        self.s.setValue("only", text.strip())
        self.win.imp.poll_cards(force=True)

    def _tray(self, on: bool):
        self.s.setValue("tray", on)
        if not on and self.c_auto.isChecked():
            self.c_auto.setChecked(False)
        self.win.update_tray()

    def _auto(self, on: bool):
        if not set_autostart(on):
            QMessageBox.warning(self, "Autostart", tr("Konnte den Autostart-Eintrag nicht ändern."))
        if on and not self.c_tray.isChecked():
            self.c_tray.setChecked(True)


# ---------------------------------------------------------------- Hauptfenster

class MainWindow(QMainWindow):
    def __init__(self, settings: QSettings):
        super().__init__()
        self.s = settings
        self._quitting = False
        self._known_roots: set[str] | None = None
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(app_icon())

        self.tabs = QTabWidget()
        self.imp = ImportTab(settings)
        self.gal = GalleryTab(settings)
        self.tabs.addTab(self.imp, tr("Importieren"))
        self.tabs.addTab(self.gal, tr("Aussortieren"))
        self.tabs.addTab(SettingsTab(settings, self), tr("Einstellungen"))
        self.setCentralWidget(self.tabs)
        self.tabs.currentChanged.connect(self._tab_changed)

        self.imp.imported.connect(self._after_import)
        self.imp.cards_changed.connect(self._cards_changed)

        self.tray = QSystemTrayIcon(app_icon(), self)
        self.tray.setToolTip(APP_NAME)
        menu = QMenu()
        a_show = QAction(tr("Öffnen"), self, triggered=self.bring_up)
        a_quit = QAction(tr("Beenden"), self, triggered=self.quit)
        menu.addAction(a_show)
        menu.addSeparator()
        menu.addAction(a_quit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(
            lambda r: self.bring_up() if r in (QSystemTrayIcon.Trigger,
                                               QSystemTrayIcon.DoubleClick) else None)
        self.tray.messageClicked.connect(self.bring_up)
        self.update_tray()

        geo = self.s.value("geometry")
        if geo:
            self.restoreGeometry(geo)
        else:
            self.resize(1000, 720)

    # ------------------------------------------------------------ Tray

    def tray_on(self) -> bool:
        return self.s.value("tray", False, type=bool) and QSystemTrayIcon.isSystemTrayAvailable()

    def update_tray(self):
        self.tray.setVisible(self.tray_on())

    def bring_up(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _cards_changed(self, cards):
        roots = {str(c.root) for c in cards}
        if self._known_roots is not None:
            new = roots - self._known_roots
            if new and self.s.value("popup", True, type=bool):
                if not self.isVisible() or self.isMinimized():
                    self.bring_up()
                self.tabs.setCurrentWidget(self.imp)
                if self.tray.isVisible():
                    self.tray.showMessage(APP_NAME,
                                          tr("Karte erkannt: {roots}", roots=", ".join(sorted(new))),
                                          app_icon(), 4000)
        self._known_roots = roots

    # ------------------------------------------------------------ Tabs

    def _tab_changed(self, i: int):
        if self.tabs.widget(i) is self.gal and self.gal.folder is None:
            self.gal.refresh_folders(self.imp.options().target_root)
            if self.gal.folder_combo.count():
                self.gal.load_folder(Path(self.gal.folder_combo.itemData(0)))

    def _after_import(self, folders):
        target = self.imp.options().target_root
        self.gal.refresh_folders(target, select=folders[-1])
        self.tabs.setCurrentWidget(self.gal)
        self.gal.load_folder(folders[-1])

    # ------------------------------------------------------------ Schließen

    def closeEvent(self, e):
        self.s.setValue("geometry", self.saveGeometry())
        if not self._quitting and self.tray_on():
            e.ignore()
            self.hide()
            return
        if not self._confirm_quit():
            e.ignore()
            self._quitting = False
            return
        self.gal.stop_loader()
        e.accept()
        QApplication.quit()

    def _confirm_quit(self) -> bool:
        if self.imp.busy():
            if QMessageBox.question(self, tr("Import läuft"),
                                    tr("Der Import läuft noch. Wirklich beenden?")) != QMessageBox.Yes:
                return False
            self.imp.cancel()
            self.imp.worker.wait(5000)
        if self.gal.has_pending_marks():
            if QMessageBox.question(self, tr("Markierungen"),
                                    tr("Es gibt markierte, aber nicht gelöschte Bilder. "
                                       "Trotzdem beenden?")) != QMessageBox.Yes:
                return False
        return True

    def quit(self):
        self._quitting = True
        self.close()

    def restart(self):
        """Programm neu starten (z. B. nach Sprachwechsel)."""
        if not self._confirm_quit():
            return
        if getattr(sys, "frozen", False):
            prog, args = sys.executable, []
        else:
            pyw = Path(sys.executable).with_name("pythonw.exe")
            prog = str(pyw if pyw.exists() else Path(sys.executable))
            args = [str(Path(sys.argv[0]).resolve())]
        if _SERVER is not None:
            _SERVER.close()  # damit die neue Instanz nicht hier andockt
        QProcess.startDetached(prog, args)
        self.gal.marked.clear()  # schon bestätigt
        self.quit()


# ---------------------------------------------------------------- Start

def main(argv=None) -> int:
    argv = list(sys.argv if argv is None else argv)
    start_hidden = "--tray" in argv

    if sys.platform == "win32":
        try:  # eigenes Taskleistensymbol statt Python-Symbol
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
        except Exception:
            pass

    app = QApplication(argv)
    early = QSettings("Leif", "DCIMImport")
    migrate_legacy(early)
    lang = set_language(early.value("lang", "auto"))
    if lang == "de":  # Standard-Dialoge (Ja/Nein, Datei-Dialog) auf Deutsch
        qt_tr = QTranslator(app)
        if qt_tr.load("qtbase_de", QLibraryInfo.path(QLibraryInfo.TranslationsPath)):
            app.installTranslator(qt_tr)
    app.setApplicationName(APP_NAME)
    app.setWindowIcon(app_icon())
    app.setQuitOnLastWindowClosed(False)

    # Einzelinstanz: läuft schon eine? Dann die nach vorne holen.
    sock = QLocalSocket()
    sock.connectToServer(APP_ID)
    if sock.waitForConnected(300):
        sock.write(b"show")
        sock.waitForBytesWritten(300)
        return 0
    QLocalServer.removeServer(APP_ID)
    global _SERVER
    server = QLocalServer()
    server.listen(APP_ID)
    _SERVER = server

    settings = early
    win = MainWindow(settings)
    app.aboutToQuit.connect(lambda: (win.imp.shutdown(), win.gal.stop_loader()))
    server.newConnection.connect(lambda: (server.nextPendingConnection(), win.bring_up()))

    if not (start_hidden and win.tray_on()):
        win.show()
    return app.exec()

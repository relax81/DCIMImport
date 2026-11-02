"""Tab „Aussortieren“: Bilder durchsehen, markieren, JPG+RAW in den Papierkorb."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QImage, QKeySequence, QPainter, QPen, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QFileDialog, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QMessageBox, QPushButton, QSlider, QVBoxLayout, QWidget,
)

from . import core
from .i18n import tr
from .workers import ThumbWorker, load_scaled

ROLE_INDEX = Qt.UserRole + 1


def mark_overlay(img: QImage, marked: bool, has_raw: bool, box: int) -> QPixmap:
    pm = QPixmap(box, box)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    if img is not None and not img.isNull():
        x, y = (box - img.width()) // 2, (box - img.height()) // 2
        p.drawImage(x, y, img)
        if marked:
            p.fillRect(x, y, img.width(), img.height(), QColor(200, 30, 30, 120))
    else:
        p.fillRect(0, 0, box, box, QColor(128, 128, 128, 60))
    if marked:
        p.setPen(QPen(QColor(255, 255, 255), max(4, box // 28)))
        m = box // 3
        p.drawLine(m, m, box - m, box - m)
        p.drawLine(box - m, m, m, box - m)
    if has_raw:  # kleines RAW-Badge unten rechts
        f = QFont()
        f.setPixelSize(max(10, box // 14))
        f.setBold(True)
        p.setFont(f)
        r = p.fontMetrics().boundingRect("RAW").adjusted(-4, -2, 4, 2)
        r.moveBottomRight(pm.rect().bottomRight())
        r.translate(-4, -4)
        p.fillRect(r, QColor(0, 0, 0, 160))
        p.setPen(QColor(255, 255, 255))
        p.drawText(r, Qt.AlignCenter, "RAW")
    p.end()
    return pm


class Viewer(QDialog):
    """Großansicht: Pfeiltasten blättern, Entf markiert, Esc schließt."""
    toggled = Signal(int)

    def __init__(self, gallery: "GalleryTab", index: int):
        super().__init__(gallery)
        self.g = gallery
        self.index = index
        self.setWindowTitle(tr("Vorschau"))
        self.setStyleSheet("background: #111; color: #ddd;")
        self.label = QLabel(alignment=Qt.AlignCenter)
        self.info = QLabel(alignment=Qt.AlignCenter)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 6)
        lay.addWidget(self.label, 1)
        lay.addWidget(self.info)
        self._img = QImage()
        self.resize(1400, 950)
        self.load()

    def load(self):
        jpg, raws = self.g.pairs[self.index]
        screen = self.screen().availableGeometry() if self.screen() else None
        box = max(screen.width(), screen.height()) if screen else 2000
        self._img = load_scaled(jpg, box)
        self.render_image()

    def render_image(self):
        jpg, raws = self.g.pairs[self.index]
        marked = jpg in self.g.marked
        if not self._img.isNull():
            pm = QPixmap.fromImage(self._img).scaled(
                self.label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            if marked:
                p = QPainter(pm)
                p.fillRect(pm.rect(), QColor(200, 30, 30, 90))
                p.end()
            self.label.setPixmap(pm)
        else:
            self.label.setText(tr("Bild konnte nicht geladen werden"))
        state = tr("  ·  ✕ MARKIERT") if marked else ""
        raw = f" + {', '.join(r.name for r in raws)}" if raws else tr("  (kein RAW)")
        self.info.setText(f"{self.index + 1}/{len(self.g.pairs)}  ·  {jpg.name}{raw}{state}"
                          + tr("     ← → blättern · Entf markieren · F Vollbild · Esc schließen"))

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.render_image()

    def keyPressEvent(self, e):
        k = e.key()
        if k in (Qt.Key_Right, Qt.Key_Down, Qt.Key_PageDown, Qt.Key_Space):
            self.go(1)
        elif k in (Qt.Key_Left, Qt.Key_Up, Qt.Key_PageUp, Qt.Key_Backspace):
            self.go(-1)
        elif k in (Qt.Key_Delete, Qt.Key_X):
            self.toggled.emit(self.index)
            self.render_image()
        elif k in (Qt.Key_F, Qt.Key_F11):
            self.showNormal() if self.isFullScreen() else self.showFullScreen()
        else:
            super().keyPressEvent(e)

    def go(self, step: int):
        n = len(self.g.pairs)
        new = max(0, min(n - 1, self.index + step))
        if new != self.index:
            self.index = new
            self.g.list.setCurrentRow(new)
            self.load()


class GalleryTab(QWidget):
    def __init__(self, settings: QSettings):
        super().__init__()
        self.s = settings
        self.folder: Path | None = None
        self.pairs: list[tuple[Path, list[Path]]] = []
        self.thumbs: dict[int, QImage] = {}
        self.marked: set[Path] = set()
        self.loader: ThumbWorker | None = None
        self.box = int(self.s.value("thumb", 180))

        # ---------- Kopfzeile
        self.folder_combo = QComboBox()
        self.folder_combo.setMinimumWidth(260)
        self.folder_combo.activated.connect(self._combo_chosen)
        btn_other = QPushButton(tr("Anderer Ordner …"))
        btn_other.clicked.connect(self.browse)
        self.zoom = QSlider(Qt.Horizontal)
        self.zoom.setRange(100, 400)
        self.zoom.setValue(self.box)
        self.zoom.setFixedWidth(140)
        self.zoom.sliderReleased.connect(self._zoom_changed)
        head = QHBoxLayout()
        head.addWidget(QLabel(tr("Ordner:")))
        head.addWidget(self.folder_combo, 1)
        head.addWidget(btn_other)
        head.addSpacing(12)
        head.addWidget(QLabel(tr("Größe")))
        head.addWidget(self.zoom)

        # ---------- Raster
        self.list = QListWidget()
        self.list.setViewMode(QListWidget.IconMode)
        self.list.setResizeMode(QListWidget.Adjust)
        self.list.setMovement(QListWidget.Static)
        self.list.setUniformItemSizes(True)
        self.list.setSpacing(6)
        self.list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        # Auswahl deutlich sichtbar: blauer Rahmen + Tönung (hell & dunkel)
        self.list.setStyleSheet("""
            QListWidget { background: palette(base); }
            QListWidget::item { border: 3px solid transparent; border-radius: 8px;
                                padding: 2px; color: palette(text); }
            QListWidget::item:hover { background: rgba(128,128,128,45); }
            QListWidget::item:selected { background: rgba(47,140,255,120);
                                         border: 3px solid #2f8cff; color: white; }
            QListWidget::item:selected:!active { background: rgba(47,140,255,90);
                                                 border: 3px solid #2f8cff; color: white; }
        """)
        self.list.itemDoubleClicked.connect(lambda it: self.open_viewer(self.list.row(it)))
        self._apply_box()

        QShortcut(QKeySequence(Qt.Key_Delete), self.list, activated=self.toggle_selected)
        QShortcut(QKeySequence(Qt.Key_X), self.list, activated=self.toggle_selected)
        QShortcut(QKeySequence(Qt.Key_Return), self.list,
                  activated=lambda: self.open_viewer(self.list.currentRow()))
        QShortcut(QKeySequence("Ctrl+Delete"), self, activated=self.trash_marked)
        QShortcut(QKeySequence(Qt.Key_Space), self.list,
                  activated=lambda: self.open_viewer(self.list.currentRow()))

        # ---------- Fußzeile
        self.info = QLabel()
        self.btn_mark = QPushButton(tr("Markieren   [Entf / X]"))
        self.btn_mark.clicked.connect(self.toggle_selected)
        self.btn_view = QPushButton(tr("Großansicht   [Leertaste]"))
        self.btn_view.clicked.connect(lambda: self.open_viewer(self.list.currentRow()))
        self.btn_trash = QPushButton(tr("Markierte in Papierkorb   [Strg+Entf]"))
        self.btn_trash.setStyleSheet("font-weight: 600;")
        self.btn_trash.clicked.connect(self.trash_marked)
        self.btn_unmark = QPushButton(tr("Alle Markierungen aufheben"))
        self.btn_unmark.clicked.connect(self.clear_marks)
        self.btn_orphans = QPushButton()
        self.btn_orphans.clicked.connect(self.trash_orphans)
        foot = QHBoxLayout()
        foot.addWidget(self.info, 1)
        foot.addWidget(self.btn_view)
        foot.addWidget(self.btn_mark)
        foot.addWidget(self.btn_orphans)
        foot.addWidget(self.btn_unmark)
        foot.addWidget(self.btn_trash)

        hint = QLabel(tr("Tasten: Pfeile wählen · Entf / X markieren · Leertaste / Enter / "
                         "Doppelklick Großansicht · Strg+A alle auswählen · Strg+Entf löschen. "
                         "Gelöscht wird erst mit „In Papierkorb“ – JPG und RAW zusammen."))
        hint.setWordWrap(True)
        pal = hint.palette()
        pal.setColor(hint.foregroundRole(), pal.color(pal.ColorRole.PlaceholderText))
        hint.setPalette(pal)

        lay = QVBoxLayout(self)
        lay.addLayout(head)
        lay.addWidget(self.list, 1)
        lay.addWidget(hint)
        lay.addLayout(foot)
        self.update_footer()

    # ------------------------------------------------------------ Ordnerwahl

    def refresh_folders(self, target_root: Path, select: Path | None = None):
        """Datumsordner des Hauptordners auflisten, neueste zuerst."""
        self.folder_combo.blockSignals(True)
        self.folder_combo.clear()
        dirs = []
        if target_root.is_dir():
            dirs = sorted((d for d in target_root.iterdir()
                           if d.is_dir() and d.name[:4].isdigit()),
                          key=lambda d: d.name, reverse=True)
        for d in dirs:
            self.folder_combo.addItem(d.name, str(d))
        if select:
            i = self.folder_combo.findData(str(select))
            if i < 0:
                self.folder_combo.insertItem(0, select.name, str(select))
                i = 0
            self.folder_combo.setCurrentIndex(i)
        self.folder_combo.blockSignals(False)

    def _combo_chosen(self, i: int):
        self.load_folder(Path(self.folder_combo.itemData(i)))

    def browse(self):
        start = str(self.folder or Path.home())
        d = QFileDialog.getExistingDirectory(self, tr("Ordner zum Aussortieren"), start)
        if d:
            p = Path(d)
            if p.name.lower() in (core.SUB_JPG, core.SUB_RAW):
                p = p.parent
            self.folder_combo.insertItem(0, p.name, str(p))
            self.folder_combo.setCurrentIndex(0)
            self.load_folder(p)

    # ------------------------------------------------------------ Laden

    def load_folder(self, folder: Path):
        if self.marked and folder != self.folder:
            if QMessageBox.question(self, tr("Markierungen verwerfen?"),
                                    tr("{n} Bilder sind markiert, aber noch nicht gelöscht. "
                                       "Trotzdem wechseln?", n=len(self.marked))) != QMessageBox.Yes:
                return
        self.stop_loader()
        self.folder = folder
        self.pairs = core.pairs_in(folder)
        self.thumbs.clear()
        self.marked.clear()
        self.list.clear()
        empty = QPixmap(self.box, self.box)
        empty.fill(QColor(128, 128, 128, 40))
        for i, (jpg, raws) in enumerate(self.pairs):
            it = QListWidgetItem(QIcon(empty), jpg.name)
            it.setData(ROLE_INDEX, i)
            it.setToolTip(jpg.name + ("  +  " + ", ".join(r.name for r in raws) if raws else
                                      tr("  (kein RAW)")))
            self.list.addItem(it)
        if self.pairs:
            self.list.setCurrentRow(0)
        self.loader = ThumbWorker([j for j, _ in self.pairs], self.box)
        self.loader.thumb.connect(self._thumb_ready)
        self.loader.start()
        self.update_footer()
        self.list.setFocus()

    def stop_loader(self):
        if self.loader and self.loader.isRunning():
            self.loader.stop()
            self.loader.wait(3000)

    def _thumb_ready(self, i: int, img: QImage):
        if i >= len(self.pairs):
            return
        self.thumbs[i] = img
        self._repaint_item(i)

    def _repaint_item(self, i: int):
        jpg, raws = self.pairs[i]
        it = self.list.item(i)
        if it:
            pm = mark_overlay(self.thumbs.get(i), jpg in self.marked, bool(raws), self.box)
            icon = QIcon(pm)
            icon.addPixmap(pm, QIcon.Selected)  # Bild bei Auswahl nicht einfärben
            it.setIcon(icon)

    def _apply_box(self):
        self.list.setIconSize(QSize(self.box, self.box))
        self.list.setGridSize(QSize(self.box + 16, self.box + 34))

    def _zoom_changed(self):
        self.box = self.zoom.value()
        self.s.setValue("thumb", self.box)
        self._apply_box()
        if self.folder:
            marked = set(self.marked)
            self.marked.clear()  # keine Rückfrage beim Neuladen
            self.load_folder(self.folder)
            self.marked = marked
            for i in range(len(self.pairs)):
                self._repaint_item(i)
            self.update_footer()

    # ------------------------------------------------------------ Markieren

    def toggle(self, i: int):
        jpg = self.pairs[i][0]
        if jpg in self.marked:
            self.marked.discard(jpg)
        else:
            self.marked.add(jpg)
        self._repaint_item(i)
        self.update_footer()

    def toggle_selected(self):
        rows = sorted(self.list.row(it) for it in self.list.selectedItems())
        if not rows:
            return
        # wenn alle markiert -> alle aufheben, sonst alle markieren
        all_marked = all(self.pairs[r][0] in self.marked for r in rows)
        for r in rows:
            jpg = self.pairs[r][0]
            (self.marked.discard if all_marked else self.marked.add)(jpg)
            self._repaint_item(r)
        self.update_footer()
        if len(rows) == 1 and rows[0] + 1 < self.list.count():
            self.list.setCurrentRow(rows[0] + 1)  # weiter zum nächsten Bild

    def clear_marks(self):
        idx = [i for i, (j, _) in enumerate(self.pairs) if j in self.marked]
        self.marked.clear()
        for i in idx:
            self._repaint_item(i)
        self.update_footer()

    def open_viewer(self, i: int):
        if not (0 <= i < len(self.pairs)):
            return
        v = Viewer(self, i)
        v.toggled.connect(self.toggle)
        v.exec()

    # ------------------------------------------------------------ Löschen

    def marked_files(self) -> list[Path]:
        out = []
        for jpg, raws in self.pairs:
            if jpg in self.marked:
                out.append(jpg)
                out.extend(raws)
        return out

    def update_footer(self):
        n_raw = sum(len(r) for j, r in self.pairs if j in self.marked)
        self.info.setText(tr("{n} Bilder · {m} markiert", n=len(self.pairs), m=len(self.marked))
                          + (tr(" (+ {n} RAW)", n=n_raw) if n_raw else ""))
        self.btn_trash.setEnabled(bool(self.marked))
        self.btn_mark.setEnabled(bool(self.pairs))
        self.btn_view.setEnabled(bool(self.pairs))
        self.btn_unmark.setEnabled(bool(self.marked))
        orphans = core.orphan_raws(self.folder) if self.folder else []
        self.btn_orphans.setText(tr("RAW ohne JPG entfernen ({n})", n=len(orphans)))
        self.btn_orphans.setEnabled(bool(orphans))
        self.btn_orphans.setToolTip("\n".join(p.name for p in orphans[:40]))

    def trash_marked(self):
        files = self.marked_files()
        if not files:
            return
        if QMessageBox.question(self, tr("In Papierkorb verschieben"),
                                tr("{n} Bilder ({m} Dateien inkl. RAW) in den Papierkorb "
                                   "verschieben?", n=len(self.marked), m=len(files))) != QMessageBox.Yes:
            return
        self._trash(files)

    def trash_orphans(self):
        if not self.folder:
            return
        orphans = core.orphan_raws(self.folder)
        if not orphans:
            return
        if QMessageBox.question(self, tr("RAW ohne JPG"),
                                tr("{n} RAW-Dateien haben kein JPG mehr. "
                                   "In den Papierkorb verschieben?", n=len(orphans))) != QMessageBox.Yes:
            return
        self._trash(orphans)

    def _trash(self, files: list[Path]):
        errors = core.to_trash(files)
        if errors:
            QMessageBox.warning(self, tr("Nicht alles gelöscht"), "\n".join(errors[:20]))
        self.marked.clear()
        keep_row = self.list.currentRow()
        self.load_folder(self.folder)
        if self.list.count():
            self.list.setCurrentRow(min(keep_row, self.list.count() - 1))

    def has_pending_marks(self) -> bool:
        return bool(self.marked)

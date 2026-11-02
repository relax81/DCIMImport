"""assets/icon.svg -> assets/icon.ico (alle Windows-Größen) und assets/icon-256.png.

Jede Größe wird direkt aus dem SVG gerendert (nicht vom großen Bild herunterskaliert),
damit 16/24/32 px scharf bleiben.  Aufruf: python tools/make_icon.py
"""
import sys
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

SIZES = [256, 128, 64, 48, 40, 32, 24, 20, 16]
ASSETS = Path(__file__).resolve().parents[1] / "assets"


def render(renderer: QSvgRenderer, size: int) -> Image.Image:
    img = QImage(size, size, QImage.Format_RGBA8888)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    renderer.render(p, QRectF(0, 0, size, size))
    p.end()
    return Image.frombuffer("RGBA", (size, size), bytes(img.constBits()), "raw", "RGBA", 0, 1)


def main() -> int:
    app = QGuiApplication.instance() or QGuiApplication(sys.argv[:1])  # noqa: F841
    renderer = QSvgRenderer(QByteArray((ASSETS / "icon.svg").read_bytes()))
    if not renderer.isValid():
        print("icon.svg ungültig")
        return 1
    images = [render(renderer, s) for s in SIZES]
    images[0].save(ASSETS / "icon-256.png")
    images[0].save(ASSETS / "icon.ico", format="ICO",
                   sizes=[(s, s) for s in SIZES], append_images=images[1:])
    print("assets/icon.ico und assets/icon-256.png geschrieben:", SIZES)
    return 0


if __name__ == "__main__":
    sys.exit(main())

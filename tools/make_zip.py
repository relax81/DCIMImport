"""ZIP mit Vorwärts-Schrägstrichen erzeugen (Compress-Archive in Windows PowerShell 5.1
schreibt Backslash-Pfade, die viele Entpacker nicht als Ordner erkennen).

Aufruf: python tools/make_zip.py <root_dir> <ordnername> <ziel.zip>
"""
import sys
import zipfile
from pathlib import Path


def main(root: Path, folder: str, dest: Path) -> int:
    src = root / folder
    if not src.is_dir():
        print(f"Ordner fehlt: {src}")
        return 1
    dest.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for p in sorted(src.rglob("*")):
            if p.is_file():
                zf.write(p, p.relative_to(root).as_posix())
                n += 1
    print(f"{n} Dateien -> {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])))

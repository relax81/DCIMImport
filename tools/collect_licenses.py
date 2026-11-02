"""Kopiert die Lizenztexte der gebündelten Pakete in einen Ordner (für das ZIP-Release)."""
import shutil
import sys
from importlib import metadata
from pathlib import Path

PACKAGES = ["PySide6", "PySide6_Essentials", "shiboken6", "Pillow", "Send2Trash", "pyinstaller"]


def main(dest: Path) -> int:
    dest.mkdir(parents=True, exist_ok=True)
    found = 0
    for pkg in PACKAGES:
        try:
            dist = metadata.distribution(pkg)
        except metadata.PackageNotFoundError:
            continue
        for f in dist.files or []:
            name = Path(str(f)).name.upper()
            if any(k in name for k in ("LICENSE", "LICENCE", "COPYING", "NOTICE")):
                src = Path(dist.locate_file(f))
                if src.is_file():
                    shutil.copy2(src, dest / f"{dist.metadata['Name']}-{src.name}")
                    found += 1
    # PySide6/Qt-Wheels enthalten keine Lizenzdateien -> LGPL/GPL-Texte aus dem Repo
    repo_lic = Path(__file__).resolve().parents[1] / "licenses"
    for f in repo_lic.glob("*.txt"):
        shutil.copy2(f, dest / f"Qt-PySide6-{f.name}")
        found += 1
    lic = Path(sys.base_prefix) / "LICENSE.txt"
    if lic.is_file():
        shutil.copy2(lic, dest / "Python-LICENSE.txt")
        found += 1
    print(f"{found} Lizenzdateien nach {dest} kopiert.")
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1])))

# Third-party licenses

DCIM Import itself is licensed under the MIT License (see `LICENSE`).
The released Windows builds (`DCIMImport.exe` and `DCIMImport-win64.zip`) bundle the
following third-party components:

| Component                                               | License                                                                   | Source                                                                      |
| ------------------------------------------------------- | ------------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| Qt for Python (PySide6, shiboken6) and the Qt libraries | GNU LGPL v3                                                               | https://code.qt.io/ · https://download.qt.io/official_releases/QtForPython/ |
| Pillow                                                  | MIT-CMU (HPND)                                                            | https://github.com/python-pillow/Pillow                                     |
| Send2Trash                                              | BSD 3-Clause                                                              | https://github.com/arsenetar/send2trash                                     |
| Python runtime                                          | PSF License                                                               | https://www.python.org/                                                     |
| PyInstaller bootloader                                  | GPL v2 with bootloader exception (allows any license for the bundled app) | https://github.com/pyinstaller/pyinstaller                                  |

The LGPL v3 and GPL v3 texts are in the `licenses` folder of this repository. The ZIP
release contains a `licenses` folder with these and the other packages' license files.

## Qt / LGPL v3

The Qt libraries are used unmodified and are linked dynamically.

- **ZIP release:** the Qt DLLs are separate files in `_internal\PySide6\` and can be
  replaced with your own (compatible) build.
- **EXE release:** the same DLLs are packed into the single file and extracted to a temporary
  folder at start. To use a different Qt build, rebuild the program from this repository
  with `build.bat` against your own PySide6/Qt installation – the complete source code
  and build script are provided here for that purpose.

The LGPL v3 text: https://www.gnu.org/licenses/lgpl-3.0.html

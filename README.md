# DCIM Import

**English** · [Deutsch](README.de.md)

Imports photos and videos from your camera's memory card into dated folders, splits JPG and RAW
and helps you cull. Works with every camera that stores images according to the DCF standard
(`DCIM\100XXXXX`) – Olympus/OM System, Canon, Nikon, Sony, Fujifilm, Panasonic, Pentax, Ricoh,
Leica and others.

Windows only. UI in English and German (automatic, or chosen in Settings).

## Download

Two variants are available under *Releases*:

- `DCIMImport.exe` – a single file, just run it.
- `DCIMImport-win64.zip` – unzip and run `DCIMImport.exe` inside the folder. Starts a bit faster.

## Run from source

Install Python 3.10+, then:

- `start.bat` – installs the dependencies on first run and starts the program.
- `build.bat` – builds `dist\DCIMImport.exe` and `dist\DCIMImport-win64.zip`.
- Tests: `python -m pytest tests`

## Import

- The card is detected automatically and all image folders on it are copied.
  The system drive is never treated as a card.
- Optionally only specific cameras (Settings → "Only these cameras", e.g. `OLYMP`),
  so that drone or action-cam cards are ignored.
- Destination: `<main folder>\YYYY-MM-DD [suffix]\jpg | raw | video`
- Optionally one folder per **capture day** (EXIF date; a RAW takes the date of the JPG with the same name).
- After copying, files are verified by size, optionally by checksum.
  Only format the card once you see the green check mark.
- Optionally eject the card.

Keys: `Ctrl+Enter` import · `Esc` cancel · `F5` rescan for cards

### Already imported?

Detected by **file name + file size**, using

1. the import history `.dcim_import_history.tsv` (hidden, in the main folder) – this also finds
   images you have culled since,
2. the files present in the main folder (including older ones not imported with this program).

Already imported files can be skipped with a checkbox.

## Review

| Key | Action |
|---|---|
| Arrow keys | select image |
| `Del` / `X` | mark / unmark |
| `Space` / `Enter` / double-click | large view (`← →` browse, `F` full screen, `Esc` back) |
| `Ctrl+A` | select all |
| `Ctrl+Del` | move marked to the Recycle Bin (JPG + matching RAW) |

**Remove RAW without JPG** cleans up folders where JPGs were already deleted elsewhere.

### Clean-up script

Every import folder gets a `delete_RAW_without_JPG.bat` (German UI: `RAW_ohne_JPG_loeschen.bat`;
can be turned off). If you delete JPGs in another image viewer: double-click it → it lists the
RAWs without a JPG and, after confirmation, moves them to the Recycle Bin.

## Settings

Language (Automatic / Deutsch / English) · keep running in the notification area · open the
window when a card is inserted · start with Windows.

## License

MIT – see [LICENSE](LICENSE). Bundled libraries and their licenses (including Qt/PySide6 under
LGPL v3): [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md).

Not affiliated with any camera maker; brand names are only used to describe compatibility.

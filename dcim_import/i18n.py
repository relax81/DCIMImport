"""Einfache Übersetzung: Deutscher Text ist der Schlüssel, Englisch steht in EN.

tr("Fertig mit {n} Fehler(n)", n=3)  ->  "Done with 3 error(s)" (wenn Englisch aktiv)
"""
from __future__ import annotations

import locale
import sys

LANGS = {"auto": "Automatisch / Automatic", "de": "Deutsch", "en": "English"}
_lang = "de"


def system_language() -> str:
    code = ""
    if sys.platform == "win32":
        try:
            import ctypes
            lcid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
            code = locale.windows_locale.get(lcid, "")
        except Exception:
            pass
    if not code:
        try:
            code = locale.getlocale()[0] or ""
        except Exception:
            code = ""
    return "de" if code.lower().startswith("de") else "en"


def set_language(choice: str) -> str:
    global _lang
    _lang = system_language() if choice in ("", "auto", None) else choice
    if _lang not in ("de", "en"):
        _lang = "en"
    return _lang


def language() -> str:
    return _lang


def tr(text: str, **kw) -> str:
    if _lang == "en":
        text = EN.get(text, text)
    return text.format(**kw) if kw else text


def date_fmt() -> str:
    return "%d.%m.%Y" if _lang == "de" else "%Y-%m-%d"


EN: dict[str, str] = {
    # ---------- Tabs / allgemein
    "Importieren": "Import",
    "Aussortieren": "Review",
    "Einstellungen": "Settings",
    "Öffnen": "Open",
    "Beenden": "Quit",
    "Karte erkannt: {roots}": "Card detected: {roots}",
    "Import läuft": "Import running",
    "Der Import läuft noch. Wirklich beenden?": "The import is still running. Quit anyway?",
    "Markierungen": "Marked images",
    "Es gibt markierte, aber nicht gelöschte Bilder. Trotzdem beenden?":
        "Some images are marked but not deleted yet. Quit anyway?",

    # ---------- Import-Tab
    "Suche Karte …": "Looking for card …",
    "Neu suchen  [F5]": "Rescan  [F5]",
    "SD-Karte": "Memory card",
    "optional, z. B. Headphone Stand": "optional, e.g. Headphone Stand",
    "Ziel": "Destination",
    "Hauptordner": "Main folder",
    "Ordner-Zusatz": "Folder suffix",
    "JPG und RAW in Unterordner aufteilen": "Split JPG and RAW into subfolders",
    "Videos in eigenen Ordner": "Put videos in their own folder",
    "Ordner nach Aufnahmedatum statt Importdatum": "Folders by capture date instead of import date",
    "Kopie per Prüfsumme kontrollieren (langsamer)": "Verify copy with checksum (slower)",
    "Karte danach auswerfen": "Eject card afterwards",
    "Danach zum Aussortieren wechseln": "Switch to Review afterwards",
    "Aufräum-Script (RAW ohne JPG) in den Ordner legen":
        "Add clean-up script (RAW without JPG) to the folder",
    "Legt {name} in jeden Importordner.\n"
    "Praktisch, wenn du JPGs später mit einem anderen Programm aussortierst:\n"
    "Doppelklick verschiebt die übrig gebliebenen RAWs in den Papierkorb.":
        "Puts {name} into every import folder.\n"
        "Handy if you cull JPGs later with another program:\n"
        "double-click it to move the leftover RAWs to the Recycle Bin.",
    "Optionen": "Options",
    "Importieren   [Strg+Enter]": "Import   [Ctrl+Enter]",
    "{n} Dateien importieren   [Strg+Enter]": "Import {n} files   [Ctrl+Enter]",
    "Nichts Neues zu importieren": "Nothing new to import",
    "Abbrechen   [Esc]": "Cancel   [Esc]",
    "Hauptordner wählen": "Choose main folder",
    "JJJJ-MM-TT": "YYYY-MM-DD",
    "  (je Aufnahmetag)": "  (one per capture day)",
    " (Filter: {only})": " (filter: {only})",
    "Keine Kamerakarte gefunden{extra}. Einstecken – wird automatisch erkannt.":
        "No camera card found{extra}. Insert one – it is detected automatically.",
    "Prüfe Karteninhalt …": "Checking card contents …",
    "Fehler: {e}": "Error: {e}",
    "Karte ist leer.": "Card is empty.",
    "{n} sonstige": "{n} other",
    "Aufnahmen vom {a}": "Taken on {a}",
    " bis {b}": " to {b}",
    "{n} Ordner": "{n} folders",
    "{n}× in „{name}“": "{n}× in “{name}”",
    "Schon importiert: {items}": "Already imported: {items}",
    "Schon importierte überspringen ({n} Dateien)": "Skip already imported ({n} files)",
    "Breche ab …": "Cancelling …",
    "Fertig mit {n} Fehler(n) – Karte NICHT formatieren, Log prüfen.":
        "Done with {n} error(s) – do NOT format the card, check the log.",
    "per Prüfsumme": "by checksum",
    "per Dateigröße": "by file size",
    "✔ {n} Dateien kopiert, {check} geprüft – Karte kann formatiert werden.":
        "✔ {n} files copied, verified {check} – the card can be formatted.",
    "Fertig.": "Done.",

    # ---------- Import-Worker
    "Lese Karte …": "Reading card …",
    "Lese Aufnahmedaten {i}/{n} …": "Reading capture dates {i}/{n} …",
    "Keine Dateien auf der Karte gefunden.": "No files found on the card.",
    "{n} Datei(en) schon importiert in „{name}“ – übersprungen.":
        "{n} file(s) already imported into “{name}” – skipped.",
    "{n} Datei(en) schon importiert in „{name}“ – werden trotzdem kopiert.":
        "{n} file(s) already imported into “{name}” – copying anyway.",
    "Nichts Neues zu kopieren.": "Nothing new to copy.",
    "Kopiere {n} Dateien ({size}) nach:": "Copying {n} files ({size}) to:",
    "FEHLER: {e}": "ERROR: {e}",
    "{n} Datei(en) lagen schon identisch im Zielordner und wurden übersprungen.":
        "{n} identical file(s) were already in the destination and were skipped.",
    "Werfe Karte aus …": "Ejecting card …",
    "Karte ausgeworfen.": "Card ejected.",
    "Karte konnte nicht ausgeworfen werden (noch in Benutzung?).":
        "Could not eject the card (still in use?).",
    "Abgebrochen. Bereits kopierte Dateien bleiben liegen.":
        "Cancelled. Files already copied are kept.",
    "Unerwarteter Fehler: {e}": "Unexpected error: {e}",
    "Größe stimmt nach dem Kopieren nicht": "size differs after copying",
    "Prüfsumme stimmt nicht": "checksum mismatch",

    # ---------- Galerie
    "Vorschau": "Preview",
    "Bild konnte nicht geladen werden": "Could not load image",
    "  ·  ✕ MARKIERT": "  ·  ✕ MARKED",
    "  (kein RAW)": "  (no RAW)",
    "     ← → blättern · Entf markieren · F Vollbild · Esc schließen":
        "     ← → browse · Del mark · F full screen · Esc close",
    "Anderer Ordner …": "Other folder …",
    "Ordner:": "Folder:",
    "Größe": "Size",
    "Markieren   [Entf / X]": "Mark   [Del / X]",
    "Großansicht   [Leertaste]": "Large view   [Space]",
    "Markierte in Papierkorb   [Strg+Entf]": "Marked to Recycle Bin   [Ctrl+Del]",
    "Alle Markierungen aufheben": "Clear all marks",
    "Tasten: Pfeile wählen · Entf / X markieren · Leertaste / Enter / Doppelklick Großansicht · "
    "Strg+A alle auswählen · Strg+Entf löschen. "
    "Gelöscht wird erst mit „In Papierkorb“ – JPG und RAW zusammen.":
        "Keys: arrows select · Del / X mark · Space / Enter / double-click large view · "
        "Ctrl+A select all · Ctrl+Del delete. "
        "Nothing is deleted until “to Recycle Bin” – JPG and RAW together.",
    "Ordner zum Aussortieren": "Folder to review",
    "Markierungen verwerfen?": "Discard marks?",
    "{n} Bilder sind markiert, aber noch nicht gelöscht. Trotzdem wechseln?":
        "{n} images are marked but not deleted yet. Switch anyway?",
    "{n} Bilder · {m} markiert": "{n} images · {m} marked",
    " (+ {n} RAW)": " (+ {n} RAW)",
    "RAW ohne JPG entfernen ({n})": "Remove RAW without JPG ({n})",
    "In Papierkorb verschieben": "Move to Recycle Bin",
    "{n} Bilder ({m} Dateien inkl. RAW) in den Papierkorb verschieben?":
        "Move {n} images ({m} files incl. RAW) to the Recycle Bin?",
    "RAW ohne JPG": "RAW without JPG",
    "{n} RAW-Dateien haben kein JPG mehr. In den Papierkorb verschieben?":
        "{n} RAW files no longer have a JPG. Move them to the Recycle Bin?",
    "Nicht alles gelöscht": "Not everything was deleted",

    # ---------- Einstellungen
    "<b>Sprache</b>": "<b>Language</b>",
    "Sprache:": "Language:",
    "Wird nach einem Neustart übernommen.": "Takes effect after a restart.",
    "Jetzt neu starten": "Restart now",
    "<b>Autostart / Hintergrund</b>": "<b>Autostart / background</b>",
    "Im Infobereich weiterlaufen, wenn das Fenster geschlossen wird":
        "Keep running in the notification area when the window is closed",
    "Fenster automatisch öffnen, wenn eine Karte eingesteckt wird":
        "Open the window automatically when a card is inserted",
    "Mit Windows starten (unsichtbar im Infobereich)":
        "Start with Windows (hidden in the notification area)",
    "„Mit Windows starten“ schaltet den Infobereich automatisch mit ein. "
    "Beenden dann über Rechtsklick aufs Symbol → Beenden.":
        "“Start with Windows” also turns on the notification area icon. "
        "To quit, right-click the icon → Quit.",
    "<b>Kameras</b>": "<b>Cameras</b>",
    "Nur diese Kameras:": "Only these cameras:",
    "leer = alle, z. B. OLYMP oder CANON, NIKON": "empty = all, e.g. OLYMP or CANON, NIKON",
    "Vergleicht mit dem Herstellerkürzel im Kartenordner "
    "(DCIM\\100<b>OLYMP</b>, 100<b>CANON</b>, 100<b>MSDCF</b> = Sony, 100<b>_FUJI</b> …). "
    "So werden z. B. Drohnen- oder Actioncam-Karten ignoriert.":
        "Matched against the maker tag in the card folder "
        "(DCIM\\100<b>OLYMP</b>, 100<b>CANON</b>, 100<b>MSDCF</b> = Sony, 100<b>_FUJI</b> …). "
        "Useful to ignore e.g. drone or action-cam cards.",
    "MIT-Lizenz": "MIT License",
    "Quellcode": "Source code",
    "Qt-Quellcode": "Qt source",
    "Verwendet Qt for Python (PySide6, {lgpl}, {qtsrc}), Pillow (MIT-CMU) und Send2Trash (BSD-3). "
    "Details in THIRD_PARTY_LICENSES.md im Repository.":
        "Uses Qt for Python (PySide6, {lgpl}, {qtsrc}), Pillow (MIT-CMU) and Send2Trash (BSD-3). "
        "Details in THIRD_PARTY_LICENSES.md in the repository.",
    "Konnte den Autostart-Eintrag nicht ändern.": "Could not change the autostart entry.",
}

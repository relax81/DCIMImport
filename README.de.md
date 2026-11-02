# DCIM Import

[English](README.md) · **Deutsch**

Importiert Fotos und Videos von der Kamera-Speicherkarte in Datumsordner, trennt JPG/RAW
und hilft beim Aussortieren. Funktioniert mit jeder Kamera, die Bilder nach DCF-Standard
ablegt (`DCIM\100XXXXX`) – Olympus/OM System, Canon, Nikon, Sony, Fujifilm, Panasonic,
Pentax, Ricoh, Leica u. a.

Nur Windows.

## Download

Unter *Releases* gibt es zwei Varianten:

- `DCIMImport.exe` – eine Datei, einfach starten.
- `DCIMImport-win64.zip` – entpacken und `DCIMImport.exe` im Ordner starten. Startet etwas schneller.

## Aus dem Quellcode starten

Python 3.10+ installieren, dann:

- `start.bat` – installiert beim ersten Mal die Abhängigkeiten und startet das Programm.
- `build.bat` – baut `dist\DCIMImport.exe` und `dist\DCIMImport-win64.zip`.
- Tests: `python -m pytest tests`

## Import

- Karte wird automatisch erkannt, alle Bildordner der Karte werden kopiert.
  Das Systemlaufwerk wird nie als Karte behandelt.
- Optional nur bestimmte Kameras (Einstellungen → „Nur diese Kameras“, z. B. `OLYMP`),
  damit z. B. Drohnen- oder Actioncam-Karten ignoriert werden.
- Ziel: `<Hauptordner>\JJJJ-MM-TT [Zusatz]\jpg | raw | video`
- Optional ein Ordner je **Aufnahmetag** (EXIF-Datum; RAW übernimmt das Datum vom gleichnamigen JPG).
- Nach dem Kopieren Prüfung per Dateigröße, optional per Prüfsumme.
  Erst beim grünen Haken die Karte formatieren.
- Optional Karte auswerfen.

Tasten: `Strg+Enter` importieren · `Esc` abbrechen · `F5` Karte neu suchen

### Schon importiert?

Erkannt an **Dateiname + Dateigröße**, über

1. die Import-Historie `.dcim_import_history.tsv` (versteckt, im Hauptordner) – findet auch
   Bilder, die inzwischen aussortiert wurden,
2. die vorhandenen Dateien im Hauptordner (auch ältere, nicht mit dem Programm importierte).

Bereits importierte Dateien können per Haken übersprungen werden.

## Aussortieren

| Taste | Aktion |
|---|---|
| Pfeiltasten | Bild wählen |
| `Entf` / `X` | markieren / Markierung aufheben |
| `Leertaste` / `Enter` / Doppelklick | Großansicht (`← →` blättern, `F` Vollbild, `Esc` zurück) |
| `Strg+A` | alle auswählen |
| `Strg+Entf` | Markierte in den Papierkorb (JPG + zugehöriges RAW) |

**RAW ohne JPG entfernen** räumt Ordner auf, in denen JPGs schon anderweitig gelöscht wurden.

### Aufräum-Script

In jeden Importordner wird `RAW_ohne_JPG_loeschen.bat` (englisch: `delete_RAW_without_JPG.bat`) gelegt (abschaltbar). Wenn du JPGs mit
einem anderen Bildbetrachter löschst: Doppelklick → listet die RAWs ohne JPG und verschiebt
sie nach Rückfrage in den Papierkorb.

## Einstellungen

Sprache (Automatisch / Deutsch / English) · Im Infobereich weiterlaufen · Fenster öffnen, wenn eine Karte eingesteckt wird ·
mit Windows starten.

## Lizenz

MIT – siehe [LICENSE](LICENSE). Verwendete Bibliotheken und ihre Lizenzen (u. a. Qt/PySide6
unter LGPL v3): [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md).

Nicht mit Kameraherstellern verbunden; Markennamen dienen nur zur Beschreibung der Kompatibilität.

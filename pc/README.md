# Phomemo P20 / D30 – Etikettendruck (PC + Android)

Bloatwarefreie Steuerung für den Phomemo **P20 / D30** Etikettendrucker via Bluetooth (BLE).
Unterstützt: **Text, QR-Codes, Barcodes, Bilder**, einstellbare **Etikettenlänge**,
**Schriftarten**, **Rahmen** und **Kabel-/Falt-Etiketten** (doppelt, gespiegelt).

Reverse-engineered aus dem GATT-Profil und Live-Tests – als schlanke Alternative
zur 122 MB großen Hersteller-App „Print Master". Die native Android-App ist **1,1 MB**.

---

## Schnellstart (PC)

```bash
# 1. Abhängigkeiten installieren
pip install -r requirements.txt

# 2. GUI starten
python gui_p20.py

# oder direkt per Kommandozeile:
python phomemo_p20.py text "Hallo Welt" --len 40
python phomemo_p20.py qr "https://example.com"
python phomemo_p20.py barcode "4006381333931" ean13
```

> Vor dem Drucken: Drucker einschalten und die App **Print Master** am Handy
> vom Drucker **trennen** (sonst ist die BLE-Verbindung belegt).

---

## Dateien

| Datei | Beschreibung |
|---|---|
| `phomemo_p20.py` | Kern-Treiber: BLE, Rendering, ESC/POS-Protokoll + CLI |
| `gui_p20.py` | Tkinter-GUI (Text/QR/Barcode/Bild, Format, Rahmen, Vorschau) |
| `icon.ico` | App-Icon |
| `LIESMICH.txt` | Endnutzer-Anleitung (liegt der portablen EXE bei) |

Eine eigenständige Windows-`.exe` baust du mit:
```bash
pyinstaller --onefile --windowed --name "Phomemo P20 Drucker" --icon icon.ico ^
  --collect-all bleak --collect-all barcode --collect-data qrcode ^
  --hidden-import PIL._tkinter_finder gui_p20.py
```

---

## Technische Eckdaten (D30/P20)

| | |
|---|---|
| BLE-Service | `ff00` · Schreibkanal `ff02` · Notify `ff03` |
| Protokoll | ESC/POS `GS v 0` Raster (`1d 76 30`), MSB-first, Init `1b 40`, Feed `1b 4a` |
| Druckbreite | **96 Dots = 12 mm** (fest), **8 Dots/mm** (203 dpi) |
| Etikettenlänge | frei wählbar (`dots = mm × 8`) |
| Rendering | Reading-Image (Länge × 96) → 90° gedreht → Raster |

Schreiben/Drucken braucht **kein** Pairing; nur der Notify-Kanal `ff03` würde
eine gebondete Verbindung verlangen (wird nicht benötigt).

---

## Eigenes Skript

```python
import asyncio
from phomemo_p20 import PhomemoP20, text_reading

async def main():
    p = PhomemoP20()
    if await p.connect():
        await p.print_text("Kabel A1", length_mm=40, font_name="Impact", frame="rund")
        await p.disconnect()

asyncio.run(main())
```

---

## Android-App

Die native, debloatete Android-App liegt im Schwesterordner
[`../phomemo_p20_android/`](../phomemo_p20_android/) (Kotlin, 1,1 MB).
Gleicher Funktionsumfang inkl. Kabel-/Falt-Etiketten.

---

## Etikettenformate

Standard-D30-Größen (12×30/40/50, 14×25/28/30/40/50, 15×30/50 mm) sowie
**Kabel-Etiketten 12,5 × 74 (einfach)** und **14 × 74 (doppelt/Falt)** sind als
Presets hinterlegt. Beim Falt-Etikett wird der Inhalt zweimal gedruckt –
zweite Hälfte um 180° gedreht, damit er nach dem Falten ums Kabel von beiden
Seiten lesbar ist.

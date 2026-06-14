# China Label Printer — auf PC & Android

Bloatwarefreie Steuerung für günstige China-Etikettendrucker via Bluetooth (BLE) —
als schlanke Alternative zu den überladenen Hersteller-Apps.

Aktuell unterstützt: **Phomemo P20 / D30** (12 mm Etiketten).
Reverse-engineered aus GATT-Profil und Live-Tests.

| | |
|---|---|
| 🖥️ **[`pc/`](pc/)** | Windows-Programm (Python/Tkinter) + portable `.exe` |
| 📱 **[`android/`](android/)** | Native Android-App (Kotlin), **1,1 MB** statt 122 MB Hersteller-App |

---

## ⬇️ Fertige Programme herunterladen

Keine Installation, kein Build nötig:

| Plattform | Download | Hinweis |
|---|---|---|
| 📱 **Android** | **[releases/Phomemo-P20.apk](releases/Phomemo-P20.apk)** | APK herunterladen → öffnen → installieren (Installation aus unbekannten Quellen erlauben) |
| 🖥️ **Windows** | **[releases/Phomemo-P20-Portable.zip](releases/Phomemo-P20-Portable.zip)** | Entpacken → `Phomemo P20 Drucker.exe` per Doppelklick (läuft auch vom USB-Stick) |

> Beide Programme sind unsigniert (Eigenbau). Android: „Trotzdem installieren".
> Windows: SmartScreen → „Weitere Informationen" → „Trotzdem ausführen".

---

## Funktionen (beide Plattformen)

- **Text** (mehrere Schriftarten, proportionaler Auto-Zoom)
- **QR-Codes** & **Barcodes** (EAN13, Code128, Code39, EAN8, UPC-A, ITF)
- **Bilder** (mit Dithering)
- **Einstellbare Etikettenlänge** + Format-Presets
- **Rahmen** (mehrere Stile)
- **Kabel-/Falt-Etiketten** (Inhalt doppelt, zweite Hälfte um 180° gedreht —
  nach dem Falten ums Kabel von beiden Seiten lesbar)
- **Kopien** & **Live-Vorschau**

---

## Schnellstart

**PC:**
```bash
cd pc
pip install -r requirements.txt
python gui_p20.py
```

**Android:**
```bash
cd android
echo "sdk.dir=/pfad/zum/Android/Sdk" > local.properties
gradle assembleDebug
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

Details in [`pc/README.md`](pc/README.md) und [`android/README.md`](android/README.md).

---

## Technik (Phomemo P20 / D30)

- BLE-Service `ff00`, Schreibkanal `ff02` (kein Pairing nötig)
- Protokoll: ESC/POS `GS v 0` Raster (`1d 76 30`), MSB-first, Init `1b 40`, Feed `1b 4a`
- Druckbreite **96 Dots = 12 mm**, **8 Dots/mm** (203 dpi)
- Rendering: Reading-Image (Länge × 96) → 90° gedreht → Raster

---

## Lizenz

Siehe [LICENSE](LICENSE).

> Hinweis: Reine, sauber selbst implementierte Ansteuerung. Keine Hersteller-Software,
> keine extrahierten App-Inhalte im Repo.

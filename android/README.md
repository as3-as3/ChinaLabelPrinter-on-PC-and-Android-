# Phomemo P20 / D30 – Android-App (debloatet)

Schlanke, native Android-App (Kotlin) zum Drucken auf dem Phomemo **P20 / D30**
via Bluetooth (BLE). Funktionsgleich mit der PC-Version, aber **1,1 MB** statt
122 MB Hersteller-App („Print Master") – ohne Tracking, Werbung, Cloud-Zwang.

Unterstützt: **Text** (7 Schriftarten), **QR**, **Barcode** (EAN13/Code128/…),
einstellbare **Etikettenlänge** + Presets, **Rahmen**, **Kabel-/Falt-Etiketten**
(doppelt, gespiegelt), **Kopien** und **Live-Vorschau**.

---

## Bauen

Voraussetzungen: Android SDK (compileSdk 34, build-tools 34), JDK 17+ (z. B. die
Android-Studio-JBR), Gradle 8.9+.

```bash
# SDK-Pfad eintragen
echo "sdk.dir=/pfad/zum/Android/Sdk" > local.properties

# Debug-APK bauen
gradle assembleDebug
# -> app/build/outputs/apk/debug/app-debug.apk

# Auf ein angeschlossenes Gerät installieren
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

Auf Windows mit der Android-Studio-Toolchain:
```powershell
$env:JAVA_HOME = "C:\Program Files\Android\Android Studio\jbr"
gradle assembleDebug
```

---

## Projektstruktur

| Datei | Beschreibung |
|---|---|
| `app/src/main/java/.../MainActivity.kt` | UI (programmatisch), Verbinden/Drucken |
| `app/src/main/java/.../Render.kt` | Rendering: Text/QR/Barcode → GS-v0-Raster, Rahmen, Falt-Etikett |
| `app/src/main/java/.../PrinterBle.kt` | BLE: Scan „D30" → ff02 (chunked schreiben) |
| `app/src/main/AndroidManifest.xml` | BLE-Berechtigungen (SCAN/CONNECT) |

Einzige externe Abhängigkeit: `com.google.zxing:core` (QR/Barcode).

---

## Berechtigungen

Beim ersten „Verbinden" fragt die App **Bluetooth-Berechtigungen** an
(`BLUETOOTH_SCAN`/`BLUETOOTH_CONNECT` ab Android 12, sonst Standort für BLE-Scan).
Es werden **keine** Internet-/Standortdaten gesendet – reine lokale BLE-Kommunikation.

---

## Drucker-Protokoll

Siehe die ausführliche Beschreibung in der PC-Version
([`../phomemo_p20/README.md`](../phomemo_p20/README.md)): ESC/POS `GS v 0`,
96 Dots / 12 mm, 8 Dots/mm, Schreibkanal `ff02` (kein Pairing nötig).

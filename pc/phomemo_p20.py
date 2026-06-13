"""
Phomemo P20 / D30 — BLE Etikettendrucker-Treiber (bloatwarefrei)
================================================================
Reverse-engineered (GATT + Live-Tests). Referenz-App: Print Master.

GERÄT: BLE-Name "D30", Service ff00
  ff02 (write-no-resp)  -> Befehle + Bitmap
  ff03 (notify)         -> Status (braucht Pairing; fürs Drucken nicht nötig)

PROTOKOLL:
  Init:   1b 40                         (ESC @)
  Bitmap: 1d 76 30 00 xL xH yL yH <data>   (ESC/POS GS v 0 Raster, MSB-first)
  Feed:   1b 4a NN                       (ESC J, NN Dots vorschieben)

GEOMETRIE:
  Tape = 96 Dots quer (12 mm), 8 Dots/mm (203 dpi).
  "Reading-Image" = Länge(Dots) x 96. Wird 90° gedreht -> 96 x Länge -> Raster.
  Etikettenlänge frei wählbar (mm).
"""
import asyncio, os
from bleak import BleakClient, BleakScanner
from PIL import Image, ImageDraw, ImageFont
import qrcode
import barcode as _barcode
from barcode.writer import ImageWriter

# ─── Gerät / Geometrie ───────────────────────────────────────────────────────
ADDRESS     = "EF:86:51:19:FA:9D"
TARGET_NAME = "D30"
WRITE_UUID  = "0000ff02-0000-1000-8000-00805f9b34fb"
NOTIFY_UUID = "0000ff03-0000-1000-8000-00805f9b34fb"

TAPE_DOTS    = 96            # 12 mm quer
TAPE_BYTES   = TAPE_DOTS // 8
DOTS_PER_MM  = 8            # 203 dpi
DEFAULT_LEN_MM = 40
CHUNK        = 180

def mm_to_dots(mm: float) -> int:
    return max(1, round(mm * DOTS_PER_MM))

# ─── Befehle ─────────────────────────────────────────────────────────────────
CMD_INIT = bytes([0x1b, 0x40])
def cmd_feed(dots: int) -> bytes:
    return bytes([0x1b, 0x4a, max(0, min(255, dots))])

def gs_v0(rows: list[bytes]) -> bytes:
    h = len(rows); w = TAPE_BYTES
    return bytes([0x1d,0x76,0x30,0x00, w&0xFF,(w>>8)&0xFF, h&0xFF,(h>>8)&0xFF]) + b"".join(rows)

# ─── Reading-Image -> Raster ─────────────────────────────────────────────────
def reading_to_rows(reading: Image.Image, threshold: int = 128) -> list[bytes]:
    """Reading-Image (Länge x 96) -> 90° gedreht -> 1bpp-Zeilen (MSB-first)."""
    g = reading.convert("L")
    rot = g.rotate(90, expand=True)              # -> 96 x Länge
    if rot.size[0] != TAPE_DOTS:
        rot = rot.resize((TAPE_DOTS, rot.size[1]), Image.LANCZOS)
    px = rot.load(); w, h = rot.size
    rows = []
    for y in range(h):
        row = bytearray(TAPE_BYTES)
        for x in range(TAPE_DOTS):
            if px[x, y] < threshold:
                row[x >> 3] |= (0x80 >> (x & 7))   # MSB-first
        rows.append(bytes(row))
    return rows

# ─── Schriftarten ────────────────────────────────────────────────────────────
_FONT_DIR = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
FONT_FILES = {
    "Arial":           ("arial.ttf",   "arialbd.ttf"),
    "Calibri":         ("calibri.ttf", "calibrib.ttf"),
    "Times New Roman": ("times.ttf",   "timesbd.ttf"),
    "Courier New":     ("cour.ttf",    "courbd.ttf"),
    "Verdana":         ("verdana.ttf", "verdanab.ttf"),
    "Georgia":         ("georgia.ttf", "georgiab.ttf"),
    "Comic Sans MS":   ("comic.ttf",   "comicbd.ttf"),
    "Impact":          ("impact.ttf",  "impact.ttf"),
    "Segoe UI":        ("segoeui.ttf", "segoeuib.ttf"),
    "Consolas":        ("consola.ttf", "consolab.ttf"),
    "Trebuchet MS":    ("trebuc.ttf",  "trebucbd.ttf"),
    "Tahoma":          ("tahoma.ttf",  "tahomabd.ttf"),
}
def available_fonts() -> list[str]:
    out = [n for n,(r,b) in FONT_FILES.items() if os.path.exists(os.path.join(_FONT_DIR, r))]
    return out or ["Arial"]

def _font(size, font_name="Arial", bold=True):
    files = FONT_FILES.get(font_name, FONT_FILES["Arial"])
    for cand in ((files[1] if bold else files[0]), files[0]):
        for path in (os.path.join(_FONT_DIR, cand), cand):
            try: return ImageFont.truetype(path, size)
            except Exception: continue
    return ImageFont.load_default()

# ─── Inhalt erzeugen (Reading-Images) ────────────────────────────────────────

def text_reading(text: str, length_mm: float | None = None, margin: int = 8,
                 font_name: str = "Arial") -> Image.Image:
    """Text passend skaliert. Länge automatisch (None) oder fix (mm).
    Bei fester Länge wird die Schrift so verkleinert, dass der Text in
    Höhe (96 Dots) UND Länge passt. font_name aus available_fonts()."""
    lines = text.split("\n")
    n = max(1, len(lines))
    dummy = ImageDraw.Draw(Image.new("L", (8, 8)))
    # Schriftgröße zunächst aus der Höhe
    fsize = max(10, (TAPE_DOTS - 2*margin) // n)
    font = _font(fsize, font_name)
    text_w = max((dummy.textlength(ln, font=font) for ln in lines), default=1)

    if length_mm is None:
        # Auto: Länge folgt dem Text
        L = int(text_w) + 4*margin
    else:
        L = mm_to_dots(length_mm)
        avail = L - 2*margin
        if text_w > avail:                      # zu breit -> Schrift verkleinern
            fsize = max(8, int(fsize * avail / text_w))
            font = _font(fsize, font_name)
            text_w = max((dummy.textlength(ln, font=font) for ln in lines), default=1)

    img = Image.new("L", (max(L, 8), TAPE_DOTS), 255)
    d = ImageDraw.Draw(img)
    line_h = fsize + 2
    total_h = n * line_h
    y = (TAPE_DOTS - total_h)//2
    for ln in lines:
        w = d.textlength(ln, font=font)
        d.text(((img.size[0]-w)//2, y), ln, font=font, fill=0)
        y += line_h
    return img

def qr_reading(data: str, length_mm: float | None = None) -> Image.Image:
    qr = qrcode.QRCode(border=1, error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(data); qr.make(fit=True)
    q = qr.make_image(fill_color="black", back_color="white").convert("L")
    q = q.resize((TAPE_DOTS, TAPE_DOTS), Image.NEAREST)
    L = mm_to_dots(length_mm) if length_mm else TAPE_DOTS
    img = Image.new("L", (max(L, TAPE_DOTS), TAPE_DOTS), 255)
    img.paste(q, ((img.size[0]-TAPE_DOTS)//2, 0))
    return img

BARCODE_TYPES = ["code128", "code39", "ean13", "ean8", "upca", "itf"]
def barcode_reading(data: str, kind: str = "code128", length_mm: float | None = None) -> Image.Image:
    bc = _barcode.get(kind, data, writer=ImageWriter())
    raw = bc.render({"module_height": 8.0, "module_width": 0.25,
                     "quiet_zone": 1.0, "write_text": False}).convert("L")
    # Barcode quer über die Länge, Höhe = 70 Dots, Text darunter
    bw, bh = raw.size
    target_h = 64
    raw = raw.resize((bw, target_h))
    L = mm_to_dots(length_mm) if length_mm else (bw + 24)
    img = Image.new("L", (max(L, bw+8, 32), TAPE_DOTS), 255)
    bx = (img.size[0] - bw)//2
    img.paste(raw, (bx, 2))
    # Klartext darunter
    code = bc.get_fullcode()
    font = _font(18, bold=False)
    d = ImageDraw.Draw(img)
    tw = d.textlength(code, font=font)
    d.text(((img.size[0]-tw)//2, target_h+6), code, font=font, fill=0)
    return img

def image_reading(img: Image.Image, length_mm: float | None = None) -> Image.Image:
    g = img.convert("L")
    # auf 96 Höhe skalieren
    w, h = g.size
    nw = max(1, round(w * TAPE_DOTS / h))
    g = g.resize((nw, TAPE_DOTS), Image.LANCZOS)
    if length_mm:
        L = mm_to_dots(length_mm)
        canvas = Image.new("L", (max(L, 8), TAPE_DOTS), 255)
        canvas.paste(g, ((canvas.size[0]-nw)//2, 0))
        return canvas
    return g

# ─── Rahmen (auf Reading-Image, 96 Dots hoch) ────────────────────────────────
FRAME_STYLES = ["kein", "solid", "doppelt", "gestrichelt", "gepunktet", "rund"]

def _dashed(d, box, dash=12, gap=7, w=2):
    x0,y0,x1,y1 = box
    def line(a,b,horiz,fix):
        p=a
        while p<b:
            q=min(p+dash,b)
            d.line([p,fix,q,fix] if horiz else [fix,p,fix,q], fill=0, width=w); p=q+gap
    line(x0,x1,True,y0); line(x0,x1,True,y1); line(y0,y1,False,x0); line(y0,y1,False,x1)

def _dotted(d, box, step=9, r=2):
    x0,y0,x1,y1 = box
    def dot(x,y): d.ellipse([x-r,y-r,x+r,y+r], fill=0)
    x=x0
    while x<=x1: dot(x,y0); dot(x,y1); x+=step
    y=y0
    while y<=y1: dot(x0,y); dot(x1,y); y+=step

def frame_reading(img: Image.Image, style: str = "kein", inset: int = 2, thick: int = 2) -> Image.Image:
    """Zeichnet einen Rahmen nahe der Etikettenkante. Inhalt wird minimal
    verkleinert, damit nichts kollidiert (proportional zentriert)."""
    if not style or style == "kein":
        return img
    img = img.convert("L")
    L, H = img.size
    pad = inset + thick + 4
    # Inhalt proportional einpassen (Zoom), zentriert
    iw, ih = L - 2*pad, H - 2*pad
    if iw < 8 or ih < 8:
        return img
    scale = min(iw / L, ih / H)
    content = img.resize((max(1,int(L*scale)), max(1,int(H*scale))), Image.LANCZOS)
    canvas = Image.new("L", (L, H), 255)
    canvas.paste(content, ((L-content.size[0])//2, (H-content.size[1])//2))
    d = ImageDraw.Draw(canvas)
    box = [inset, inset, L-1-inset, H-1-inset]
    if style == "solid":
        d.rectangle(box, outline=0, width=thick)
    elif style == "doppelt":
        d.rectangle(box, outline=0, width=1)
        d.rectangle([box[0]+4,box[1]+4,box[2]-4,box[3]-4], outline=0, width=1)
    elif style == "rund":
        d.rounded_rectangle(box, radius=10, outline=0, width=thick)
    elif style == "gestrichelt":
        _dashed(d, box, w=thick)
    elif style == "gepunktet":
        _dotted(d, box)
    return canvas

# ─── Etiketten-Formate (aus Print Master localPaper.json + Druckverlauf) ─────
# (Anzeigename, Länge mm oder None=auto, Modus 'single'|'double')
LABEL_PRESETS: list[tuple[str, float | None, str]] = [
    ("Auto (Länge folgt Inhalt)", None, "single"),
    ("12 × 30 mm", 30, "single"),
    ("12 × 40 mm", 40, "single"),
    ("12 × 50 mm", 50, "single"),
    ("14 × 25 mm", 25, "single"),
    ("14 × 28 mm", 28, "single"),
    ("14 × 30 mm", 30, "single"),
    ("14 × 40 mm", 40, "single"),
    ("14 × 50 mm", 50, "single"),
    ("15 × 30 mm", 30, "single"),
    ("15 × 50 mm", 50, "single"),
    ("Kabel 12,5 × 74 (einfach)", 74, "single"),
    ("Kabel 14 × 74 (doppelt/Falt)", 74, "double"),
]
PRESET_NAMES = [p[0] for p in LABEL_PRESETS]
def preset_by_name(name: str) -> tuple[float | None, str]:
    for n, l, m in LABEL_PRESETS:
        if n == name:
            return l, m
    return None, "single"

def double_fold_reading(content: Image.Image, length_mm: float, margin_frac: float = 0.14) -> Image.Image:
    """Falt-Kabel-Etikett: Inhalt zweimal — Hälfte 1 aufrecht, Hälfte 2 um 180° gedreht.
    Innen-/Außenränder bleiben leer (Wickelteil)."""
    L = mm_to_dots(length_mm)
    half = L // 2
    canvas = Image.new("L", (L, TAPE_DOTS), 255)
    c = content.convert("L")
    avail_w = max(8, int(half * (1 - 2 * margin_frac)))
    avail_h = TAPE_DOTS - 10
    scale = min(avail_w / c.size[0], avail_h / c.size[1])
    cw, ch = max(1, int(c.size[0] * scale)), max(1, int(c.size[1] * scale))
    c = c.resize((cw, ch), Image.LANCZOS)
    y = (TAPE_DOTS - ch) // 2
    canvas.paste(c, ((half - cw) // 2, y))                  # Hälfte 1 aufrecht
    canvas.paste(c.rotate(180), (half + (half - cw) // 2, y))  # Hälfte 2 um 180°
    return canvas

# ─── Drucker ─────────────────────────────────────────────────────────────────
class PhomemoP20:
    def __init__(self):
        self.client: BleakClient | None = None
        self.feed_dots = 24     # Vorschub nach Druck (Abrisskante)

    async def connect(self, address: str = ADDRESS) -> bool:
        print(f"Scanne nach {TARGET_NAME}...")
        found = None
        def cb(d, a):
            nonlocal found
            if d.address == address or (d.name and TARGET_NAME in (d.name or "")):
                found = d.address
        sc = BleakScanner(detection_callback=cb)
        await sc.start(); await asyncio.sleep(6); await sc.stop()
        if not found:
            print("Drucker nicht gefunden! Print Master getrennt?"); return False
        print(f"Verbinde mit {found}...")
        self.client = BleakClient(found, timeout=20.0)
        await self.client.connect()
        print(f"Verbunden! MTU={self.client.mtu_size}")
        return True

    async def disconnect(self):
        if self.client and self.client.is_connected:
            await self.client.disconnect(); print("Getrennt.")

    async def _send(self, data: bytes):
        for i in range(0, len(data), CHUNK):
            await self.client.write_gatt_char(WRITE_UUID, data[i:i+CHUNK], response=False)
            await asyncio.sleep(0.02)

    async def print_reading(self, reading: Image.Image, copies: int = 1):
        rows = reading_to_rows(reading)
        print(f"Etikett: {reading.size[0]} Dots lang ({reading.size[0]/DOTS_PER_MM:.0f} mm), {len(rows)} Rasterzeilen, {copies}x")
        for n in range(copies):
            if copies > 1: print(f"  Kopie {n+1}/{copies}")
            await self._send(CMD_INIT); await asyncio.sleep(0.15)
            await self._send(gs_v0(rows)); await asyncio.sleep(0.15)
            await self._send(cmd_feed(self.feed_dots)); await asyncio.sleep(0.6)
        print("Fertig.")

    async def print_text(self, text, length_mm=None, copies=1, font_name="Arial", frame="kein"):
        await self.print_reading(frame_reading(text_reading(text, length_mm, font_name=font_name), frame), copies)
    async def print_qr(self, data, length_mm=None, copies=1, frame="kein"):
        await self.print_reading(frame_reading(qr_reading(data, length_mm), frame), copies)
    async def print_barcode(self, data, kind="code128", length_mm=None, copies=1, frame="kein"):
        await self.print_reading(frame_reading(barcode_reading(data, kind, length_mm), frame), copies)
    async def print_image_file(self, path, length_mm=None, copies=1, frame="kein"):
        await self.print_reading(frame_reading(image_reading(Image.open(path), length_mm), frame), copies)

# ─── CLI ─────────────────────────────────────────────────────────────────────
def _usage():
    print("""Phomemo P20/D30 — Verwendung:
  python phomemo_p20.py text "Text"          Text (Länge automatisch)
  python phomemo_p20.py qr   "daten"
  python phomemo_p20.py barcode "123" [typ]
  python phomemo_p20.py image bild.png
  python phomemo_p20.py test

Optionen:
  --len MM        feste Etikettenlänge in mm (sonst automatisch)
  --copies N      N Kopien
  --font NAME     Schriftart (z.B. "Arial", "Impact", "Courier New")
  --frame STIL    Rahmen: solid, doppelt, gestrichelt, gepunktet, rund
Barcode-Typen: code128, code39, ean13, ean8, upca, itf
""")

async def main():
    import sys
    args = sys.argv[1:]
    length_mm, copies, font_name, frame = None, 1, "Arial", "kein"
    rest = []
    i = 0
    while i < len(args):
        if args[i] == "--len" and i+1 < len(args): length_mm = float(args[i+1]); i += 2
        elif args[i] == "--copies" and i+1 < len(args): copies = int(args[i+1]); i += 2
        elif args[i] == "--font" and i+1 < len(args): font_name = args[i+1]; i += 2
        elif args[i] == "--frame" and i+1 < len(args): frame = args[i+1]; i += 2
        else: rest.append(args[i]); i += 1
    args = rest
    mode = args[0].lower() if args else "test"
    if mode in ("help","-h","--help"): _usage(); return

    p = PhomemoP20()
    if not await p.connect(): return
    try:
        if mode == "text":     await p.print_text(args[1].replace("\\n","\n"), length_mm, copies, font_name, frame)
        elif mode == "qr":     await p.print_qr(args[1], length_mm, copies, frame)
        elif mode == "barcode":await p.print_barcode(args[1], args[2] if len(args)>2 else "code128", length_mm, copies, frame)
        elif mode == "image":  await p.print_image_file(args[1], length_mm, copies, frame)
        else:                  await p.print_text("P20 TEST\nPhomemo D30", length_mm, copies, font_name, frame)
    finally:
        await p.disconnect()

if __name__ == "__main__":
    asyncio.run(main())

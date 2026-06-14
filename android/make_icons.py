"""Erzeugt schöne Android-Launcher-Icons (adaptiv + Legacy) für die P20-App.
Motiv: Etikettendrucker mit herauskommendem Etikett (Barcode) auf blauem Verlauf."""
import os, math
from PIL import Image, ImageDraw, ImageFilter

# Farben
BG_TOP   = (138, 180, 250)   # helles Blau
BG_BOT   = (74, 120, 208)    # tiefes Blau
PRINTER  = (30, 33, 54)      # Carbon
PRINTER2 = (52, 58, 90)      # Carbon hell
WHITE    = (248, 250, 255)
INK      = (24, 26, 40)
ACCENT   = (137, 200, 255)

def rounded_mask(size, radius):
    m = Image.new("L", (size, size), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, size-1, size-1], radius=radius, fill=255)
    return m

def gradient(size, c1, c2):
    g = Image.new("RGB", (size, size), c1)
    d = ImageDraw.Draw(g)
    for y in range(size):
        t = y / size
        col = tuple(int(c1[i]*(1-t) + c2[i]*t) for i in range(3))
        d.line([(0, y), (size, y)], fill=col)
    return g

def draw_motif(img, S, fg_only=False):
    """Zeichnet Drucker + Etikett, zentriert. fg_only: nur Motiv (für adaptiven Vordergrund)."""
    d = ImageDraw.Draw(img, "RGBA")
    cx = S/2
    # Etikett (kommt oben aus dem Drucker), leicht angehoben
    lw, lh = S*0.50, S*0.34
    lx0, ly0 = cx - lw/2, S*0.16
    lx1, ly1 = cx + lw/2, ly0 + lh
    # Schatten
    sh = Image.new("RGBA", img.size, (0,0,0,0))
    ImageDraw.Draw(sh).rounded_rectangle([lx0, ly0+S*0.02, lx1, ly1+S*0.02], radius=S*0.04, fill=(0,0,0,70))
    sh = sh.filter(ImageFilter.GaussianBlur(S*0.02))
    img.alpha_composite(sh)
    d.rounded_rectangle([lx0, ly0, lx1, ly1], radius=S*0.035, fill=WHITE)
    # Barcode auf dem Etikett
    bx = lx0 + S*0.05
    bw = S*0.014
    heights = [0.6,0.4,0.6,0.35,0.55,0.6,0.4,0.5,0.45,0.6,0.4,0.55]
    bcx = bx
    i = 0
    while bcx < lx1 - S*0.05 and i < len(heights):
        hh = heights[i]
        bh = lh*0.42*hh
        ccy = ly0 + lh*0.34
        d.rectangle([bcx, ccy - bh/2, bcx + bw, ccy + bh/2], fill=INK)
        bcx += bw*1.7; i += 1
    # zwei Textlinien
    d.rounded_rectangle([lx0+S*0.05, ly1-lh*0.30, lx0+lw*0.7, ly1-lh*0.22], radius=S*0.01, fill=INK)
    d.rounded_rectangle([lx0+S*0.05, ly1-lh*0.17, lx0+lw*0.5, ly1-lh*0.09], radius=S*0.01, fill=(120,128,150))

    # Drucker-Korpus unten
    pw, ph = S*0.62, S*0.30
    px0, py0 = cx - pw/2, S*0.52
    px1, py1 = cx + pw/2, py0 + ph
    d.rounded_rectangle([px0, py0, px1, py1], radius=S*0.05, fill=PRINTER)
    # Schlitz (wo das Etikett rauskommt)
    d.rounded_rectangle([cx - lw/2 - S*0.01, py0 - S*0.018, cx + lw/2 + S*0.01, py0 + S*0.03],
                        radius=S*0.015, fill=PRINTER2)
    d.rounded_rectangle([cx - lw/2, py0 + S*0.002, cx + lw/2, py0 + S*0.016], radius=S*0.008, fill=(10,11,20))
    # Status-LED + Linie
    d.ellipse([px0+S*0.05, py1-S*0.085, px0+S*0.05+S*0.04, py1-S*0.045], fill=ACCENT)
    d.rounded_rectangle([px0+S*0.13, py1-S*0.075, px1-S*0.06, py1-S*0.055], radius=S*0.01, fill=(70,78,110))

def compose(S):
    """Komplettes Icon (Hintergrund + Motiv), volle Fläche."""
    base = gradient(S, BG_TOP, BG_BOT).convert("RGBA")
    draw_motif(base, S)
    return base

def foreground(S):
    """Nur Motiv auf transparent, mit Safe-Zone-Padding (für adaptiven Vordergrund)."""
    img = Image.new("RGBA", (S, S), (0,0,0,0))
    # Motiv in zentrale ~72/108 zeichnen -> auf kleinerer Fläche rendern und einsetzen
    inner = int(S*0.66)
    sub = Image.new("RGBA", (inner, inner), (0,0,0,0))
    draw_motif(sub, inner)
    img.alpha_composite(sub, ((S-inner)//2, (S-inner)//2))
    return img

def circle_mask(size):
    m = Image.new("L", (size, size), 0)
    ImageDraw.Draw(m).ellipse([0, 0, size-1, size-1], fill=255)
    return m

def generate(res_dir):
    # Master in hoher Auflösung
    master_full = compose(1024)
    master_fg = foreground(864)   # 432*2 für scharfe Skalierung

    dens = {  # density: (launcher px, foreground px)
        "mdpi":    (48, 108),
        "hdpi":    (72, 162),
        "xhdpi":   (96, 216),
        "xxhdpi":  (144, 324),
        "xxxhdpi": (192, 432),
    }
    for dn, (lp, fp) in dens.items():
        folder = os.path.join(res_dir, f"mipmap-{dn}")
        os.makedirs(folder, exist_ok=True)
        # Legacy quadratisch (leicht gerundet)
        sq = master_full.resize((lp, lp), Image.LANCZOS)
        msq = rounded_mask(lp, int(lp*0.22))
        outsq = Image.new("RGBA", (lp, lp), (0,0,0,0)); outsq.paste(sq, (0,0), msq)
        outsq.save(os.path.join(folder, "ic_launcher.png"))
        # Legacy rund
        rnd = master_full.resize((lp, lp), Image.LANCZOS)
        outr = Image.new("RGBA", (lp, lp), (0,0,0,0)); outr.paste(rnd, (0,0), circle_mask(lp))
        outr.save(os.path.join(folder, "ic_launcher_round.png"))
        # Adaptiver Vordergrund
        fg = master_fg.resize((fp, fp), Image.LANCZOS)
        fg.save(os.path.join(folder, "ic_launcher_foreground.png"))
    print(f"Icons generiert in {res_dir}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "gen":
        generate(os.path.join("app", "src", "main", "res"))
    else:
        compose(512).save("_icon_preview.png")
        full = compose(512); m = rounded_mask(512, 110)
        out = Image.new("RGBA", (512,512), (0,0,0,0)); out.paste(full, (0,0), m)
        out.save("_icon_preview_rounded.png")
        print("Vorschau erstellt. 'python make_icons.py gen' schreibt die res-Icons.")

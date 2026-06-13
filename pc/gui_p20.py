#!/usr/bin/env python3
"""
Phomemo P20 / D30 — GUI (Tkinter), bloatwarefrei.
Tabs: Text · QR · Barcode · Bild — mit einstellbarer Etikettenlänge + Live-Vorschau.
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import asyncio, threading
from PIL import Image, ImageTk

import phomemo_p20 as pp
from phomemo_p20 import (PhomemoP20, text_reading, qr_reading, barcode_reading,
                         image_reading, frame_reading, double_fold_reading,
                         BARCODE_TYPES, TAPE_DOTS, DOTS_PER_MM, FRAME_STYLES,
                         available_fonts, PRESET_NAMES, preset_by_name)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Phomemo P20 / D30 — Etikettendruck")
        self.geometry("620x680")
        self.configure(bg="#1E1E2E")
        self.printer = None
        self.connected = False
        self._pimg = None
        self._loop = asyncio.new_event_loop()
        threading.Thread(target=self._loop.run_forever, daemon=True).start()
        self._build()

    def _run(self, coro, done=None):
        fut = asyncio.run_coroutine_threadsafe(coro, self._loop)
        def cb(f):
            e = f.exception()
            if e: self.after(0, lambda: self._log(f"Fehler: {e}"))
            elif done: self.after(0, done)
        fut.add_done_callback(cb)

    def _log(self, m): self.status.config(text=m)

    def _build(self):
        st = ttk.Style(self); st.theme_use("clam")
        bg, fg, acc = "#1E1E2E", "#CDD6F4", "#89B4FA"
        st.configure("TFrame", background=bg)
        st.configure("TLabel", background=bg, foreground=fg, font=("Segoe UI", 10))
        st.configure("TButton", background="#313244", foreground=fg, font=("Segoe UI", 10), padding=6)
        st.configure("TCheckbutton", background=bg, foreground=fg)
        st.configure("TRadiobutton", background=bg, foreground=fg)
        st.configure("TNotebook", background=bg, borderwidth=0)
        st.configure("TNotebook.Tab", background="#313244", foreground=fg, padding=(14,6))
        st.map("TNotebook.Tab", background=[("selected", acc)], foreground=[("selected", "#1E1E2E")])
        st.configure("Accent.TButton", background=acc, foreground="#1E1E2E", font=("Segoe UI", 11, "bold"))

        top = ttk.Frame(self); top.pack(fill="x", padx=14, pady=10)
        self.btn_conn = ttk.Button(top, text="🔗 Verbinden", command=self._toggle, style="Accent.TButton")
        self.btn_conn.pack(side="left")
        self.conn_lbl = ttk.Label(top, text="● getrennt", foreground="#F38BA8"); self.conn_lbl.pack(side="left", padx=12)

        nb = ttk.Notebook(self); nb.pack(fill="both", expand=True, padx=14)
        self.tabs = nb

        # Text
        f1 = ttk.Frame(nb); nb.add(f1, text="Text")
        ttk.Label(f1, text="Text (mehrzeilig):").pack(anchor="w", pady=(10,2))
        self.txt = tk.Text(f1, height=4, bg="#313244", fg=fg, insertbackground=fg, font=("Segoe UI", 11))
        self.txt.pack(fill="x"); self.txt.insert("1.0", "Hallo Welt")
        frow = ttk.Frame(f1); frow.pack(fill="x", pady=(8,0))
        ttk.Label(frow, text="Schriftart:").pack(side="left")
        self.font_name = tk.StringVar(value="Arial")
        fonts = available_fonts()
        if "Arial" not in fonts: self.font_name.set(fonts[0])
        fcb = ttk.Combobox(frow, textvariable=self.font_name, values=fonts, state="readonly", width=20)
        fcb.pack(side="left", padx=8)
        fcb.bind("<<ComboboxSelected>>", lambda e: self._preview())

        # QR
        f2 = ttk.Frame(nb); nb.add(f2, text="QR-Code")
        ttk.Label(f2, text="QR-Inhalt:").pack(anchor="w", pady=(10,2))
        self.qr = tk.Entry(f2, bg="#313244", fg=fg, insertbackground=fg, font=("Segoe UI", 11))
        self.qr.pack(fill="x"); self.qr.insert(0, "https://example.com")

        # Barcode
        f3 = ttk.Frame(nb); nb.add(f3, text="Barcode")
        ttk.Label(f3, text="Barcode-Inhalt:").pack(anchor="w", pady=(10,2))
        self.bc = tk.Entry(f3, bg="#313244", fg=fg, insertbackground=fg, font=("Segoe UI", 11))
        self.bc.pack(fill="x"); self.bc.insert(0, "4006381333931")
        ttk.Label(f3, text="Typ:").pack(anchor="w", pady=(8,2))
        self.bc_type = tk.StringVar(value="ean13")
        ttk.Combobox(f3, textvariable=self.bc_type, values=BARCODE_TYPES, state="readonly").pack(fill="x")

        # Bild
        f4 = ttk.Frame(nb); nb.add(f4, text="Bild")
        self.img_path = tk.StringVar(value="(keine Datei)")
        ttk.Button(f4, text="📁 Bilddatei wählen…", command=self._pick).pack(pady=10)
        ttk.Label(f4, textvariable=self.img_path, wraplength=560).pack()

        nb.bind("<<NotebookTabChanged>>", lambda e: self._preview())
        for w in (self.txt,): w.bind("<KeyRelease>", lambda e: self._preview())
        for w in (self.qr, self.bc): w.bind("<KeyRelease>", lambda e: self._preview())

        # Format-Preset
        pf = ttk.Frame(self); pf.pack(fill="x", padx=14, pady=(10,0))
        ttk.Label(pf, text="Format:").pack(side="left")
        self.preset = tk.StringVar(value=PRESET_NAMES[2])  # 12x40
        self.mode = "single"
        pcb = ttk.Combobox(pf, textvariable=self.preset, values=PRESET_NAMES, state="readonly", width=28)
        pcb.pack(side="left", padx=8)
        pcb.bind("<<ComboboxSelected>>", lambda e: self._apply_preset())

        # Etikettenlänge + Kopien
        opt = ttk.Frame(self); opt.pack(fill="x", padx=14, pady=(8,0))
        self.auto_len = tk.BooleanVar(value=False)
        ttk.Checkbutton(opt, text="Länge automatisch", variable=self.auto_len,
                        command=self._preview).grid(row=0, column=0, sticky="w")
        ttk.Label(opt, text="Etikettenlänge (mm):").grid(row=0, column=1, sticky="w", padx=(14,4))
        self.length = tk.IntVar(value=40)
        ttk.Spinbox(opt, from_=10, to=300, textvariable=self.length, width=6,
                    command=self._preview).grid(row=0, column=2)
        ttk.Label(opt, text="Kopien:").grid(row=0, column=3, sticky="w", padx=(14,4))
        self.copies = tk.IntVar(value=1)
        ttk.Spinbox(opt, from_=1, to=99, textvariable=self.copies, width=5).grid(row=0, column=4)
        ttk.Label(opt, text="Rahmen:").grid(row=1, column=0, sticky="w", pady=(8,0))
        self.frame_style = tk.StringVar(value="kein")
        rcb = ttk.Combobox(opt, textvariable=self.frame_style, values=FRAME_STYLES,
                           state="readonly", width=14)
        rcb.grid(row=1, column=1, columnspan=2, sticky="w", padx=4, pady=(8,0))
        rcb.bind("<<ComboboxSelected>>", lambda e: self._preview())

        ttk.Label(self, text="Vorschau (12 mm Tape, Länge ×):").pack(anchor="w", padx=14, pady=(10,2))
        self.canvas = tk.Label(self, bg="white"); self.canvas.pack(padx=14)

        ttk.Button(self, text="🖨  DRUCKEN", command=self._print, style="Accent.TButton").pack(fill="x", padx=14, pady=12)
        self.status = ttk.Label(self, text="Bereit. Drucker an, Print Master getrennt.", foreground="#A6E3A1")
        self.status.pack(padx=14, pady=(0,10))
        self.after(200, self._preview)

    def _apply_preset(self):
        length, mode = preset_by_name(self.preset.get())
        self.mode = mode
        if length is None:
            self.auto_cb_set(True)
        else:
            self.auto_cb_set(False)
            self.length.set(int(length))
        self._preview()

    def auto_cb_set(self, val: bool):
        self.auto_len.set(val)

    def _len(self):
        return None if self.auto_len.get() else self.length.get()

    def _content(self, L):
        tab = self.tabs.tab(self.tabs.select(), "text")
        if tab == "Text":
            return text_reading(self.txt.get("1.0","end").strip() or " ", L, font_name=self.font_name.get())
        if tab == "QR-Code":
            return qr_reading(self.qr.get().strip() or " ", L)
        if tab == "Barcode":
            return barcode_reading(self.bc.get().strip() or "0", self.bc_type.get(), L)
        if tab == "Bild":
            p = self.img_path.get()
            if p and p != "(keine Datei)":
                return image_reading(Image.open(p), L)
        return None

    def _reading(self):
        if self.mode == "double":
            # Inhalt natürlich rendern, dann in beide Hälften falten
            c = self._content(None)
            if c is None: return None
            length = self.length.get() or 74
            return double_fold_reading(c, length)
        r = self._content(self._len())
        if r is not None:
            r = frame_reading(r, self.frame_style.get())
        return r

    def _preview(self):
        try:
            r = self._reading()
        except Exception as e:
            self._log(f"Vorschau: {e}"); return
        if r is None: return
        # Vorschau wie das echte Etikett (Länge waagerecht), max 560 breit
        disp = r.convert("L")
        scale = min(4.0, 560 / disp.size[0])
        disp = disp.resize((max(1,int(disp.size[0]*scale)), int(TAPE_DOTS*scale)), Image.NEAREST)
        self._pimg = ImageTk.PhotoImage(disp)
        self.canvas.config(image=self._pimg)

    def _pick(self):
        p = filedialog.askopenfilename(filetypes=[("Bilder","*.png *.jpg *.jpeg *.bmp *.gif")])
        if p: self.img_path.set(p); self._preview()

    def _toggle(self):
        if self.connected:
            self._run(self.printer.disconnect(), self._dis)
        else:
            self._log("Verbinde… (Drucker an, Print Master getrennt)")
            self.printer = PhomemoP20()
            self._run(self.printer.connect(), self._con)

    def _con(self):
        self.connected = True
        self.conn_lbl.config(text="● verbunden", foreground="#A6E3A1")
        self.btn_conn.config(text="✖ Trennen"); self._log("Verbunden. Bereit.")
    def _dis(self):
        self.connected = False
        self.conn_lbl.config(text="● getrennt", foreground="#F38BA8")
        self.btn_conn.config(text="🔗 Verbinden"); self._log("Getrennt.")

    def _print(self):
        if not self.connected:
            messagebox.showwarning("Nicht verbunden", "Bitte zuerst verbinden."); return
        try:
            r = self._reading()
        except Exception as e:
            messagebox.showerror("Fehler", str(e)); return
        if r is None:
            messagebox.showwarning("Kein Inhalt", "Nichts zu drucken."); return
        n = self.copies.get()
        self._log(f"Drucke {n}x …")
        self._run(self.printer.print_reading(r, copies=n), lambda: self._log("Druck fertig ✓"))


if __name__ == "__main__":
    App().mainloop()

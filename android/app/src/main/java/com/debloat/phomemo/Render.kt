package com.debloat.phomemo

import android.graphics.*
import com.google.zxing.BarcodeFormat
import com.google.zxing.MultiFormatWriter
import com.google.zxing.qrcode.QRCodeWriter
import java.io.ByteArrayOutputStream
import kotlin.math.max
import kotlin.math.roundToInt

/**
 * Rendering für Phomemo P20/D30.
 * Tape = 96 Dots quer (12 mm), 8 Dots/mm. Reading-Image (Länge x 96) wird
 * 90° gedreht -> 96 x Länge -> ESC/POS GS v 0 (MSB-first).
 */
object Render {
    const val TAPE_DOTS = 96
    const val BYTES_PER_ROW = TAPE_DOTS / 8
    const val DOTS_PER_MM = 8

    val FONTS = linkedMapOf(
        "Standard" to Typeface.create(Typeface.SANS_SERIF, Typeface.BOLD),
        "Serif" to Typeface.create(Typeface.SERIF, Typeface.BOLD),
        "Monospace" to Typeface.create(Typeface.MONOSPACE, Typeface.BOLD),
        "Schmal" to Typeface.create("sans-serif-condensed", Typeface.BOLD),
        "Fett" to Typeface.create("sans-serif-black", Typeface.NORMAL),
        "Leicht" to Typeface.create(Typeface.SANS_SERIF, Typeface.NORMAL),
        "Kursiv" to Typeface.create(Typeface.SANS_SERIF, Typeface.BOLD_ITALIC)
    )
    val FONT_NAMES = FONTS.keys.toList()

    val FRAMES = listOf("kein", "solid", "doppelt", "gestrichelt", "gepunktet", "rund")

    val BARCODES = linkedMapOf(
        "code128" to BarcodeFormat.CODE_128,
        "code39" to BarcodeFormat.CODE_39,
        "ean13" to BarcodeFormat.EAN_13,
        "ean8" to BarcodeFormat.EAN_8,
        "upca" to BarcodeFormat.UPC_A,
        "itf" to BarcodeFormat.ITF
    )

    fun mmToDots(mm: Float): Int = max(1, (mm * DOTS_PER_MM).roundToInt())

    // ── Text ────────────────────────────────────────────────────────────────
    fun textReading(text: String, lengthDots: Int?, typeface: Typeface, frame: String): Bitmap {
        val lines = if (text.isEmpty()) listOf(" ") else text.split("\n")
        val n = max(1, lines.size)
        val margin = 8
        val paint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = Color.BLACK; this.typeface = typeface; isSubpixelText = true
        }
        var size = ((TAPE_DOTS - 2 * margin) / n).toFloat()
        paint.textSize = size
        var textW = lines.maxOf { paint.measureText(it) }

        val L: Int
        if (lengthDots == null) {
            L = (textW + 4 * margin).toInt()
        } else {
            L = lengthDots
            val avail = (L - 2 * margin).toFloat()
            if (textW > avail) {
                size = max(8f, size * avail / textW)
                paint.textSize = size
                textW = lines.maxOf { paint.measureText(it) }
            }
        }
        val bmp = Bitmap.createBitmap(max(L, 8), TAPE_DOTS, Bitmap.Config.ARGB_8888)
        val c = Canvas(bmp); c.drawColor(Color.WHITE)
        val fm = paint.fontMetrics
        val lineH = size + 2
        val top = (TAPE_DOTS - n * lineH) / 2f
        for ((i, ln) in lines.withIndex()) {
            val w = paint.measureText(ln)
            val baseline = top + i * lineH - fm.ascent
            c.drawText(ln, (bmp.width - w) / 2f, baseline, paint)
        }
        return applyFrame(bmp, frame)
    }

    // ── QR ──────────────────────────────────────────────────────────────────
    fun qrReading(data: String, lengthDots: Int?, frame: String): Bitmap {
        val matrix = QRCodeWriter().encode(if (data.isEmpty()) " " else data,
            BarcodeFormat.QR_CODE, TAPE_DOTS, TAPE_DOTS)
        val qr = Bitmap.createBitmap(TAPE_DOTS, TAPE_DOTS, Bitmap.Config.ARGB_8888)
        for (y in 0 until TAPE_DOTS) for (x in 0 until TAPE_DOTS)
            qr.setPixel(x, y, if (matrix.get(x, y)) Color.BLACK else Color.WHITE)
        val L = lengthDots ?: TAPE_DOTS
        val bmp = Bitmap.createBitmap(max(L, TAPE_DOTS), TAPE_DOTS, Bitmap.Config.ARGB_8888)
        val c = Canvas(bmp); c.drawColor(Color.WHITE)
        c.drawBitmap(qr, ((bmp.width - TAPE_DOTS) / 2).toFloat(), 0f, null)
        return applyFrame(bmp, frame)
    }

    // ── Barcode ───────────────────────────────────────────────────────────────
    fun barcodeReading(data: String, type: String, lengthDots: Int?, frame: String): Bitmap {
        val fmt = BARCODES[type] ?: BarcodeFormat.CODE_128
        val targetW = lengthDots ?: 280
        val barH = 64
        val matrix = MultiFormatWriter().encode(if (data.isEmpty()) "0" else data, fmt,
            targetW - 16, barH)
        val mw = matrix.width; val mh = matrix.height
        val bc = Bitmap.createBitmap(mw, mh, Bitmap.Config.ARGB_8888)
        for (y in 0 until mh) for (x in 0 until mw)
            bc.setPixel(x, y, if (matrix.get(x, y)) Color.BLACK else Color.WHITE)
        val L = lengthDots ?: (mw + 24)
        val bmp = Bitmap.createBitmap(max(L, mw + 8), TAPE_DOTS, Bitmap.Config.ARGB_8888)
        val c = Canvas(bmp); c.drawColor(Color.WHITE)
        c.drawBitmap(bc, ((bmp.width - mw) / 2).toFloat(), 2f, null)
        // Klartext darunter
        val paint = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = Color.BLACK; textSize = 18f }
        val tw = paint.measureText(data)
        c.drawText(data, (bmp.width - tw) / 2f, (barH + 22).toFloat(), paint)
        return applyFrame(bmp, frame)
    }

    // ── Rahmen ────────────────────────────────────────────────────────────────
    fun applyFrame(img: Bitmap, style: String): Bitmap {
        if (style == "kein" || style.isEmpty()) return img
        val L = img.width; val H = img.height
        val inset = 2f; val thick = 2f; val pad = inset + thick + 4f
        val iw = L - 2 * pad; val ih = H - 2 * pad
        if (iw < 8 || ih < 8) return img
        val scale = minOf(iw / L, ih / H)
        val cw = max(1, (L * scale).toInt()); val ch = max(1, (H * scale).toInt())
        val content = Bitmap.createScaledBitmap(img, cw, ch, true)
        val out = Bitmap.createBitmap(L, H, Bitmap.Config.ARGB_8888)
        val c = Canvas(out); c.drawColor(Color.WHITE)
        c.drawBitmap(content, ((L - cw) / 2).toFloat(), ((H - ch) / 2).toFloat(), null)
        val p = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = Color.BLACK; this.style = Paint.Style.STROKE; strokeWidth = thick
        }
        val l = inset; val t = inset; val r = L - 1 - inset; val b = H - 1 - inset
        when (style) {
            "solid" -> c.drawRect(l, t, r, b, p)
            "doppelt" -> { p.strokeWidth = 1f; c.drawRect(l, t, r, b, p); c.drawRect(l + 4, t + 4, r - 4, b - 4, p) }
            "rund" -> c.drawRoundRect(l, t, r, b, 10f, 10f, p)
            "gestrichelt" -> { p.pathEffect = DashPathEffect(floatArrayOf(12f, 7f), 0f); c.drawRect(l, t, r, b, p) }
            "gepunktet" -> { p.pathEffect = DashPathEffect(floatArrayOf(2f, 7f), 0f); p.strokeCap = Paint.Cap.ROUND; p.strokeWidth = 3f; c.drawRect(l, t, r, b, p) }
        }
        return out
    }

    // ── Reading-Bitmap -> GS v 0 Raster ──────────────────────────────────────
    fun toGsV0(reading: Bitmap): ByteArray {
        val m = Matrix().apply { postRotate(-90f) }   // CCW (wie PIL rotate(90))
        var rot = Bitmap.createBitmap(reading, 0, 0, reading.width, reading.height, m, true)
        if (rot.width != TAPE_DOTS) {
            rot = Bitmap.createScaledBitmap(rot, TAPE_DOTS, rot.height, true)
        }
        val w = TAPE_DOTS; val h = rot.height
        val pixels = IntArray(w * h)
        rot.getPixels(pixels, 0, w, 0, 0, w, h)
        val out = ByteArrayOutputStream()
        out.write(byteArrayOf(0x1d, 0x76, 0x30, 0x00,
            (BYTES_PER_ROW and 0xFF).toByte(), ((BYTES_PER_ROW shr 8) and 0xFF).toByte(),
            (h and 0xFF).toByte(), ((h shr 8) and 0xFF).toByte()))
        for (y in 0 until h) {
            val row = ByteArray(BYTES_PER_ROW)
            for (x in 0 until w) {
                val px = pixels[y * w + x]
                val lum = (Color.red(px) * 30 + Color.green(px) * 59 + Color.blue(px) * 11) / 100
                if (lum < 128) {
                    row[x shr 3] = (row[x shr 3].toInt() or (0x80 shr (x and 7))).toByte()
                }
            }
            out.write(row)
        }
        return out.toByteArray()
    }

    // ── Etiketten-Formate (aus Print Master extrahiert) ─────────────────────
    data class Preset(val name: String, val lengthMm: Int?, val mode: String)
    val PRESETS = listOf(
        Preset("Auto (Länge folgt Inhalt)", null, "single"),
        Preset("12 × 30 mm", 30, "single"),
        Preset("12 × 40 mm", 40, "single"),
        Preset("12 × 50 mm", 50, "single"),
        Preset("14 × 25 mm", 25, "single"),
        Preset("14 × 28 mm", 28, "single"),
        Preset("14 × 30 mm", 30, "single"),
        Preset("14 × 40 mm", 40, "single"),
        Preset("14 × 50 mm", 50, "single"),
        Preset("15 × 30 mm", 30, "single"),
        Preset("15 × 50 mm", 50, "single"),
        Preset("Kabel 12,5 × 74 (einfach)", 74, "single"),
        Preset("Kabel 14 × 74 (doppelt/Falt)", 74, "double")
    )
    val PRESET_NAMES = PRESETS.map { it.name }

    /** Falt-Kabel-Etikett: Inhalt zweimal — Hälfte 1 aufrecht, Hälfte 2 um 180°. */
    fun doubleFoldReading(content: Bitmap, lengthDots: Int, marginFrac: Float = 0.14f): Bitmap {
        val half = lengthDots / 2
        val out = Bitmap.createBitmap(lengthDots, TAPE_DOTS, Bitmap.Config.ARGB_8888)
        val c = Canvas(out); c.drawColor(Color.WHITE)
        val availW = max(8, (half * (1 - 2 * marginFrac)).toInt())
        val availH = TAPE_DOTS - 10
        val scale = minOf(availW.toFloat() / content.width, availH.toFloat() / content.height)
        val cw = max(1, (content.width * scale).toInt())
        val ch = max(1, (content.height * scale).toInt())
        val scaled = Bitmap.createScaledBitmap(content, cw, ch, true)
        val y = ((TAPE_DOTS - ch) / 2).toFloat()
        c.drawBitmap(scaled, ((half - cw) / 2).toFloat(), y, null)
        val m = Matrix().apply { postRotate(180f) }
        val rot = Bitmap.createBitmap(scaled, 0, 0, cw, ch, m, true)
        c.drawBitmap(rot, (half + (half - cw) / 2).toFloat(), y, null)
        return out
    }

    val CMD_INIT = byteArrayOf(0x1b, 0x40)
    fun cmdFeed(dots: Int) = byteArrayOf(0x1b, 0x4a, dots.coerceIn(0, 255).toByte())
}

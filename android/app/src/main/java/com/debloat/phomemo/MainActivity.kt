package com.debloat.phomemo

import android.Manifest
import android.app.Activity
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.graphics.Color
import android.os.Build
import android.os.Bundle
import android.text.InputType
import android.view.Gravity
import android.view.View
import android.widget.*

class MainActivity : Activity(), PrinterBle.Listener {

    private lateinit var ble: PrinterBle
    private lateinit var statusTv: TextView
    private lateinit var connectBtn: Button
    private lateinit var typeSp: Spinner
    private lateinit var contentEt: EditText
    private lateinit var fontSp: Spinner
    private lateinit var barcodeSp: Spinner
    private lateinit var frameSp: Spinner
    private lateinit var formatSp: Spinner
    private lateinit var lenEt: EditText
    private lateinit var autoCb: CheckBox
    private lateinit var copiesEt: EditText
    private lateinit var preview: ImageView
    private var connected = false
    private var mode = "single"

    private fun dp(v: Int) = (v * resources.displayMetrics.density).toInt()

    override fun onCreate(s: Bundle?) {
        super.onCreate(s)
        ble = PrinterBle(this).also { it.listener = this }

        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(16), dp(16), dp(16), dp(16))
        }
        val scroll = ScrollView(this).apply { addView(root) }

        fun label(t: String) = TextView(this).apply {
            text = t; setPadding(0, dp(10), 0, dp(2)); setTextColor(Color.DKGRAY)
        }

        // Kopf
        val title = TextView(this).apply {
            text = "Phomemo P20 / D30"; textSize = 20f; setTextColor(Color.BLACK)
            setTypeface(typeface, android.graphics.Typeface.BOLD)
        }
        root.addView(title)

        connectBtn = Button(this).apply { text = "Verbinden"; setOnClickListener { onConnect() } }
        root.addView(connectBtn)
        statusTv = TextView(this).apply { text = "Bereit. Drucker an, Print Master getrennt."; setPadding(0, dp(4), 0, dp(4)) }
        root.addView(statusTv)

        // Typ
        root.addView(label("Inhalt"))
        typeSp = Spinner(this).apply {
            adapter = sa(listOf("Text", "QR-Code", "Barcode"))
            onItemSelected { updateVisibility(); updatePreview() }
        }
        root.addView(typeSp)

        contentEt = EditText(this).apply {
            setText("Hallo Welt"); inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_FLAG_MULTI_LINE
            hint = "Text / Daten"; afterTextChanged { updatePreview() }
        }
        root.addView(contentEt)

        // Schriftart
        val fontLbl = label("Schriftart"); root.addView(fontLbl)
        fontSp = Spinner(this).apply { adapter = sa(Render.FONT_NAMES); onItemSelected { updatePreview() } }
        root.addView(fontSp)

        // Barcode-Typ
        val bcLbl = label("Barcode-Typ"); root.addView(bcLbl)
        barcodeSp = Spinner(this).apply { adapter = sa(Render.BARCODES.keys.toList()); onItemSelected { updatePreview() } }
        root.addView(barcodeSp)
        bcLbl.tag = "bc"; barcodeSp.tag = "bc"

        // Rahmen
        root.addView(label("Rahmen"))
        frameSp = Spinner(this).apply { adapter = sa(Render.FRAMES); onItemSelected { updatePreview() } }
        root.addView(frameSp)

        // Format-Preset
        root.addView(label("Format"))
        formatSp = Spinner(this).apply {
            adapter = sa(Render.PRESET_NAMES)
            onItemSelected { applyPreset() }
        }
        root.addView(formatSp)

        // Länge + Kopien
        root.addView(label("Etikettenlänge (mm) / Kopien"))
        val row = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        autoCb = CheckBox(this).apply { text = "Auto"; setOnCheckedChangeListener { _, _ -> updatePreview() } }
        lenEt = EditText(this).apply {
            setText("40"); inputType = InputType.TYPE_CLASS_NUMBER; width = dp(70); afterTextChanged { updatePreview() }
        }
        copiesEt = EditText(this).apply {
            setText("1"); inputType = InputType.TYPE_CLASS_NUMBER; width = dp(60)
        }
        row.addView(autoCb); row.addView(TextView(this).apply { text = "  mm:" }); row.addView(lenEt)
        row.addView(TextView(this).apply { text = "  Kopien:" }); row.addView(copiesEt)
        root.addView(row)

        // Vorschau
        root.addView(label("Vorschau"))
        preview = ImageView(this).apply {
            setBackgroundColor(Color.WHITE); setPadding(dp(4), dp(4), dp(4), dp(4))
            adjustViewBounds = true; minimumHeight = dp(60)
        }
        root.addView(preview)

        // Drucken
        root.addView(Button(this).apply {
            text = "DRUCKEN"; setOnClickListener { onPrint() }
            val lp = LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT)
            lp.topMargin = dp(12); layoutParams = lp
        })

        setContentView(scroll)
        updateVisibility()
        preview.post { updatePreview() }
    }

    private fun sa(items: List<String>) =
        ArrayAdapter(this, android.R.layout.simple_spinner_dropdown_item, items)

    private fun updateVisibility() {
        val t = typeSp.selectedItem?.toString() ?: "Text"
        val isText = t == "Text"; val isBc = t == "Barcode"
        fontSp.visibility = if (isText) View.VISIBLE else View.GONE
        barcodeSp.visibility = if (isBc) View.VISIBLE else View.GONE
    }

    private fun lengthDots(): Int? = if (autoCb.isChecked) null
        else Render.mmToDots((lenEt.text.toString().toFloatOrNull() ?: 40f))

    private fun applyPreset() {
        if (!::lenEt.isInitialized || !::autoCb.isInitialized) return
        val p = Render.PRESETS.getOrNull(formatSp.selectedItemPosition) ?: return
        mode = p.mode
        if (p.lengthMm == null) autoCb.isChecked = true
        else { autoCb.isChecked = false; lenEt.setText(p.lengthMm.toString()) }
        updatePreview()
    }

    private fun buildContent(lengthDots: Int?, frame: String): Bitmap? {
        val t = typeSp.selectedItem?.toString() ?: "Text"
        val data = contentEt.text.toString()
        return when (t) {
            "Text" -> Render.textReading(data, lengthDots,
                Render.FONTS[fontSp.selectedItem?.toString()] ?: Render.FONTS.values.first(), frame)
            "QR-Code" -> Render.qrReading(data, lengthDots, frame)
            "Barcode" -> Render.barcodeReading(data, barcodeSp.selectedItem?.toString() ?: "code128", lengthDots, frame)
            else -> null
        }
    }

    private fun buildReading(): Bitmap? = try {
        if (mode == "double") {
            val c = buildContent(null, "kein")
            if (c == null) null else {
                val len = lenEt.text.toString().toIntOrNull() ?: 74
                Render.doubleFoldReading(c, Render.mmToDots(len.toFloat()))
            }
        } else {
            buildContent(lengthDots(), frameSp.selectedItem?.toString() ?: "kein")
        }
    } catch (e: Exception) { statusTv.text = "Vorschau: ${e.message}"; null }

    private fun updatePreview() {
        val b = buildReading() ?: return
        preview.setImageBitmap(b)
    }

    // ── Verbinden / Drucken ─────────────────────────────────────────────────
    private val PERMS = if (Build.VERSION.SDK_INT >= 31)
        arrayOf(Manifest.permission.BLUETOOTH_SCAN, Manifest.permission.BLUETOOTH_CONNECT)
    else arrayOf(Manifest.permission.ACCESS_FINE_LOCATION)

    private fun hasPerms() = PERMS.all { checkSelfPermission(it) == PackageManager.PERMISSION_GRANTED }

    private fun onConnect() {
        if (connected) { ble.disconnect(); return }
        if (!hasPerms()) { requestPermissions(PERMS, 1); return }
        ble.connect()
    }

    override fun onRequestPermissionsResult(rc: Int, p: Array<out String>, r: IntArray) {
        super.onRequestPermissionsResult(rc, p, r)
        if (hasPerms()) ble.connect() else statusTv.text = "Bluetooth-Berechtigung nötig"
    }

    private fun onPrint() {
        if (!connected) { Toast.makeText(this, "Bitte zuerst verbinden", Toast.LENGTH_SHORT).show(); return }
        val b = buildReading() ?: return
        val copies = copiesEt.text.toString().toIntOrNull()?.coerceIn(1, 99) ?: 1
        ble.printReading(b, copies, 24)
    }

    // ── Listener ─────────────────────────────────────────────────────────────
    override fun onStatus(msg: String) { runOnUiThread { statusTv.text = msg } }
    override fun onConnected() { runOnUiThread { connected = true; connectBtn.text = "Trennen" } }
    override fun onDisconnected() { runOnUiThread { connected = false; connectBtn.text = "Verbinden" } }
    override fun onPrintDone() { runOnUiThread { statusTv.text = "Druck fertig ✓" } }

    // ── kleine Helfer ────────────────────────────────────────────────────────
    private fun Spinner.onItemSelected(cb: () -> Unit) {
        onItemSelectedListener = object : AdapterView.OnItemSelectedListener {
            override fun onItemSelected(p: AdapterView<*>?, v: View?, pos: Int, id: Long) = cb()
            override fun onNothingSelected(p: AdapterView<*>?) {}
        }
    }
    private fun EditText.afterTextChanged(cb: () -> Unit) {
        addTextChangedListener(object : android.text.TextWatcher {
            override fun beforeTextChanged(s: CharSequence?, a: Int, b: Int, c: Int) {}
            override fun onTextChanged(s: CharSequence?, a: Int, b: Int, c: Int) {}
            override fun afterTextChanged(s: android.text.Editable?) { cb() }
        })
    }
}

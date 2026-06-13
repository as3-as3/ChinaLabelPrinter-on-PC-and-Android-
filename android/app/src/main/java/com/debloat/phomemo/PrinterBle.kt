package com.debloat.phomemo

import android.annotation.SuppressLint
import android.bluetooth.*
import android.bluetooth.le.ScanCallback
import android.bluetooth.le.ScanResult
import android.content.Context
import android.os.Handler
import android.os.Looper
import java.util.*
import java.util.concurrent.ConcurrentLinkedQueue

/** BLE-Treiber für Phomemo P20/D30 (Service ff00, Schreibkanal ff02). */
@SuppressLint("MissingPermission")
class PrinterBle(private val ctx: Context) {

    interface Listener {
        fun onStatus(msg: String)
        fun onConnected()
        fun onDisconnected()
        fun onPrintDone()
    }

    var listener: Listener? = null

    private val SERVICE = UUID.fromString("0000ff00-0000-1000-8000-00805f9b34fb")
    private val WRITE   = UUID.fromString("0000ff02-0000-1000-8000-00805f9b34fb")
    private val TARGET  = "D30"

    private val main = Handler(Looper.getMainLooper())
    private val adapter: BluetoothAdapter? =
        (ctx.getSystemService(Context.BLUETOOTH_SERVICE) as BluetoothManager).adapter

    private var gatt: BluetoothGatt? = null
    private var writeChar: BluetoothGattCharacteristic? = null
    private var mtu = 20
    private val queue = ConcurrentLinkedQueue<ByteArray>()
    private var writing = false
    private var scanning = false

    fun isConnected() = writeChar != null

    private fun status(m: String) = main.post { listener?.onStatus(m) }

    // ── Scan + Connect ────────────────────────────────────────────────────────
    fun connect() {
        val ad = adapter ?: run { status("Bluetooth nicht verfügbar"); return }
        if (!ad.isEnabled) { status("Bitte Bluetooth einschalten"); return }
        status("Scanne nach $TARGET …")
        scanning = true
        ad.bluetoothLeScanner.startScan(scanCb)
        main.postDelayed({
            if (scanning) {
                scanning = false
                try { ad.bluetoothLeScanner.stopScan(scanCb) } catch (_: Exception) {}
                if (!isConnected()) status("Drucker nicht gefunden. An? Print Master getrennt?")
            }
        }, 10000)
    }

    private val scanCb = object : ScanCallback() {
        override fun onScanResult(type: Int, result: ScanResult) {
            val name = result.device.name ?: result.scanRecord?.deviceName
            if (name != null && name.contains(TARGET)) {
                scanning = false
                try { adapter?.bluetoothLeScanner?.stopScan(this) } catch (_: Exception) {}
                status("Gefunden: $name — verbinde …")
                result.device.connectGatt(ctx, false, gattCb, BluetoothDevice.TRANSPORT_LE)
            }
        }
    }

    private val gattCb = object : BluetoothGattCallback() {
        override fun onConnectionStateChange(g: BluetoothGatt, st: Int, newState: Int) {
            if (newState == BluetoothProfile.STATE_CONNECTED) {
                status("Verbunden — frage MTU/Dienste ab …")
                g.requestMtu(200)
            } else if (newState == BluetoothProfile.STATE_DISCONNECTED) {
                writeChar = null; gatt = null
                main.post { listener?.onDisconnected() }
                status("Getrennt.")
            }
        }
        override fun onMtuChanged(g: BluetoothGatt, m: Int, st: Int) {
            mtu = if (m in 24..517) m else 23
            g.discoverServices()
        }
        override fun onServicesDiscovered(g: BluetoothGatt, st: Int) {
            val svc = g.getService(SERVICE)
            val ch = svc?.getCharacteristic(WRITE)
            if (ch == null) { status("Schreibkanal ff02 nicht gefunden"); return }
            ch.writeType = BluetoothGattCharacteristic.WRITE_TYPE_NO_RESPONSE
            writeChar = ch; gatt = g
            main.post { listener?.onConnected() }
            status("Bereit zum Drucken.")
        }
        override fun onCharacteristicWrite(g: BluetoothGatt, c: BluetoothGattCharacteristic, st: Int) {
            writing = false
            writeNext()
        }
    }

    fun disconnect() {
        try { gatt?.disconnect(); gatt?.close() } catch (_: Exception) {}
        gatt = null; writeChar = null
    }

    // ── Drucken ───────────────────────────────────────────────────────────────
    fun printReading(reading: android.graphics.Bitmap, copies: Int, feedDots: Int) {
        val ch = writeChar ?: run { status("Nicht verbunden"); return }
        val data = Render.toGsV0(reading)
        status("Drucke (${copies}x) …")
        Thread {
            for (n in 0 until copies) {
                enqueueChunks(Render.CMD_INIT)
                enqueueChunks(data)
                enqueueChunks(Render.cmdFeed(feedDots))
                Thread.sleep(400)
            }
            main.post { listener?.onPrintDone() }
        }.start()
    }

    private fun enqueueChunks(bytes: ByteArray) {
        val size = (mtu - 3).coerceAtLeast(18)
        var i = 0
        while (i < bytes.size) {
            queue.add(bytes.copyOfRange(i, minOf(i + size, bytes.size)))
            i += size
        }
        main.post { writeNext() }
    }

    @Suppress("DEPRECATION")
    private fun writeNext() {
        if (writing) return
        val ch = writeChar ?: return
        val chunk = queue.poll() ?: return
        writing = true
        val g = gatt ?: return
        if (android.os.Build.VERSION.SDK_INT >= 33) {
            g.writeCharacteristic(ch, chunk, BluetoothGattCharacteristic.WRITE_TYPE_NO_RESPONSE)
        } else {
            ch.value = chunk
            g.writeCharacteristic(ch)
        }
    }
}

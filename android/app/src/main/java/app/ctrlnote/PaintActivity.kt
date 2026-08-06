package app.ctrlnote

import android.content.ClipboardManager
import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Canvas as AndroidCanvas
import android.graphics.Color as AndroidColor
import android.graphics.Paint
import android.graphics.RectF
import android.net.Uri
import android.os.Bundle
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectDragGestures
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Slider
import androidx.compose.material3.SliderDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.asAndroidPath
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.IntSize
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlin.math.abs
import kotlin.math.max
import kotlin.math.min

private enum class Tool { Pen, Eraser, Line, Rect, Oval, Fill }

private sealed class DrawOp {
    data class Freehand(val path: Path, val color: Color, val width: Float) : DrawOp()
    data class LineOp(val a: Offset, val b: Offset, val color: Color, val width: Float) : DrawOp()
    data class RectOp(val a: Offset, val b: Offset, val color: Color, val width: Float) : DrawOp()
    data class OvalOp(val a: Offset, val b: Offset, val color: Color, val width: Float) : DrawOp()
}

private sealed class Hist {
    data class Op(val op: DrawOp) : Hist()
    data class Raster(val before: Bitmap, val after: Bitmap) : Hist()
}

class PaintActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        setContent {
            val accent = Color(0xFF3878FA)
            val tools = listOf(
                Tool.Pen to "Перо",
                Tool.Eraser to "Ластик",
                Tool.Line to "Линия",
                Tool.Rect to "Прямоуг",
                Tool.Oval to "Круг",
                Tool.Fill to "Заливка",
            )
            val palette = listOf(
                Color(0xFF111111),
                Color.White,
                Color(0xFFE74C3C),
                Color(0xFF2980B9),
                Color(0xFF27AE60),
                Color(0xFF8E44AD),
                Color(0xFFF39C12),
                Color(0xFFF1C40F),
            )

            var tool by remember { mutableStateOf(Tool.Pen) }
            var color by remember { mutableStateOf(Color(0xFF111111)) }
            var thickness by remember { mutableFloatStateOf(4f) }
            var canvasSize by remember { mutableStateOf(IntSize.Zero) }
            var frame by remember { mutableIntStateOf(0) }
            var start by remember { mutableStateOf<Offset?>(null) }
            var preview by remember { mutableStateOf<DrawOp?>(null) }
            var currentPath by remember { mutableStateOf<DrawOp.Freehand?>(null) }

            val ops = remember { mutableStateListOf<DrawOp>() }
            val undo = remember { mutableStateListOf<Hist>() }
            val redo = remember { mutableStateListOf<Hist>() }

            var baseBmp by remember {
                mutableStateOf(Bitmap.createBitmap(8, 8, Bitmap.Config.ARGB_8888).also {
                    it.eraseColor(AndroidColor.WHITE)
                })
            }

            fun ensureBaseSize(size: IntSize) {
                if (size.width < 2 || size.height < 2) return
                if (baseBmp.width == size.width && baseBmp.height == size.height) return
                baseBmp = Bitmap.createScaledBitmap(baseBmp, size.width, size.height, true)
                    .copy(Bitmap.Config.ARGB_8888, true)
            }

            fun pushHist(entry: Hist) {
                undo.add(entry)
                while (undo.size > 25) {
                    undo.removeAt(0)
                }
                redo.clear()
            }

            fun penWidth(): Float =
                if (tool == Tool.Eraser) max(thickness * 2f, thickness + 6f) else thickness

            fun drawColor(): Color =
                if (tool == Tool.Eraser) Color.White else color

            fun pushOp(op: DrawOp) {
                ops.add(op)
                pushHist(Hist.Op(op))
                frame++
            }

            fun applyRaster(after: Bitmap) {
                baseBmp = after.copy(Bitmap.Config.ARGB_8888, true)
                ops.clear()
                preview = null
                currentPath = null
                frame++
            }

            fun renderFlat(w: Int, h: Int): Bitmap {
                val bmp = Bitmap.createBitmap(w, h, Bitmap.Config.ARGB_8888)
                val c = AndroidCanvas(bmp)
                val src = if (baseBmp.width == w && baseBmp.height == h) {
                    baseBmp
                } else {
                    Bitmap.createScaledBitmap(baseBmp, w, h, true)
                }
                c.drawBitmap(src, 0f, 0f, null)
                val paint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
                    style = Paint.Style.STROKE
                    strokeCap = Paint.Cap.ROUND
                    strokeJoin = Paint.Join.ROUND
                }
                fun strokeColor(col: Color): Int = AndroidColor.argb(
                    (col.alpha * 255).toInt(),
                    (col.red * 255).toInt(),
                    (col.green * 255).toInt(),
                    (col.blue * 255).toInt(),
                )
                (ops + listOfNotNull(preview, currentPath)).forEach { op ->
                    when (op) {
                        is DrawOp.Freehand -> {
                            paint.color = strokeColor(op.color)
                            paint.strokeWidth = op.width
                            c.drawPath(op.path.asAndroidPath(), paint)
                        }
                        is DrawOp.LineOp -> {
                            paint.color = strokeColor(op.color)
                            paint.strokeWidth = op.width
                            c.drawLine(op.a.x, op.a.y, op.b.x, op.b.y, paint)
                        }
                        is DrawOp.RectOp -> {
                            paint.color = strokeColor(op.color)
                            paint.strokeWidth = op.width
                            c.drawRect(
                                min(op.a.x, op.b.x),
                                min(op.a.y, op.b.y),
                                max(op.a.x, op.b.x),
                                max(op.a.y, op.b.y),
                                paint,
                            )
                        }
                        is DrawOp.OvalOp -> {
                            paint.color = strokeColor(op.color)
                            paint.strokeWidth = op.width
                            c.drawOval(
                                RectF(
                                    min(op.a.x, op.b.x),
                                    min(op.a.y, op.b.y),
                                    max(op.a.x, op.b.x),
                                    max(op.a.y, op.b.y),
                                ),
                                paint,
                            )
                        }
                    }
                }
                return bmp
            }

            fun setBackground(bitmap: Bitmap) {
                val w = canvasSize.width.coerceAtLeast(1)
                val h = canvasSize.height.coerceAtLeast(1)
                if (w < 8 || h < 8) {
                    Toast.makeText(this@PaintActivity, "Подождите загрузки холста", Toast.LENGTH_SHORT).show()
                    return
                }
                val before = renderFlat(w, h)
                val fitted = fitBitmap(bitmap, w, h)
                pushHist(Hist.Raster(before, fitted))
                applyRaster(fitted)
            }

            fun doFill(x: Float, y: Float) {
                val w = canvasSize.width.coerceAtLeast(1)
                val h = canvasSize.height.coerceAtLeast(1)
                if (w < 8 || h < 8) return
                val before = renderFlat(w, h)
                val after = before.copy(Bitmap.Config.ARGB_8888, true)
                val newColor = AndroidColor.argb(
                    (color.alpha * 255).toInt(),
                    (color.red * 255).toInt(),
                    (color.green * 255).toInt(),
                    (color.blue * 255).toInt(),
                )
                floodFillBitmap(after, x.toInt(), y.toInt(), newColor, 24)
                pushHist(Hist.Raster(before, after.copy(Bitmap.Config.ARGB_8888, true)))
                applyRaster(after)
            }

            fun undoAction() {
                if (undo.isEmpty()) return
                when (val e = undo.removeAt(undo.lastIndex)) {
                    is Hist.Op -> {
                        if (ops.isNotEmpty()) ops.removeAt(ops.lastIndex)
                        redo.add(e)
                    }
                    is Hist.Raster -> {
                        applyRaster(e.before)
                        redo.add(e)
                    }
                }
                frame++
            }

            fun redoAction() {
                if (redo.isEmpty()) return
                when (val e = redo.removeAt(redo.lastIndex)) {
                    is Hist.Op -> {
                        ops.add(e.op)
                        undo.add(e)
                    }
                    is Hist.Raster -> {
                        applyRaster(e.after)
                        undo.add(e)
                    }
                }
                frame++
            }

            fun clearCanvas() {
                val w = canvasSize.width.coerceAtLeast(1)
                val h = canvasSize.height.coerceAtLeast(1)
                if (w < 8 || h < 8) return
                val before = renderFlat(w, h)
                val after = Bitmap.createBitmap(w, h, Bitmap.Config.ARGB_8888).also {
                    it.eraseColor(AndroidColor.WHITE)
                }
                pushHist(Hist.Raster(before, after))
                applyRaster(after)
            }

            val imagePicker = rememberLauncherForActivityResult(
                ActivityResultContracts.GetContent(),
            ) { uri: Uri? ->
                if (uri == null) return@rememberLauncherForActivityResult
                decodeBitmap(this@PaintActivity, uri)?.let { setBackground(it) }
                    ?: Toast.makeText(this@PaintActivity, "Не удалось открыть изображение", Toast.LENGTH_SHORT).show()
            }

            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .background(Color(0xFF1A1A1A))
                    .padding(10.dp),
            ) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .horizontalScroll(rememberScrollState()),
                    horizontalArrangement = Arrangement.spacedBy(6.dp),
                ) {
                    tools.forEach { (t, label) ->
                        FilterChip(
                            selected = tool == t,
                            onClick = { tool = t },
                            label = { Text(label, fontSize = 12.sp) },
                        )
                    }
                }

                Spacer(Modifier = Modifier.height(8.dp))

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(6.dp),
                ) {
                    palette.forEach { c ->
                        val selected = c == color
                        val borderCol = when {
                            selected -> accent
                            c == Color(0xFF111111) -> Color(0xFFDDDDDD)
                            c == Color.White -> Color(0xFF888888)
                            else -> Color(0xFF666666)
                        }
                        Box(
                            modifier = Modifier
                                .size(30.dp)
                                .border(
                                    width = if (selected) 3.dp else 2.dp,
                                    color = borderCol,
                                    shape = CircleShape,
                                )
                                .background(c, CircleShape)
                                .clickable {
                                    color = c
                                    if (tool == Tool.Eraser) tool = Tool.Pen
                                },
                        )
                    }
                    Spacer(modifier = Modifier.weight(1f))
                    Text("${thickness.toInt()} px", color = Color(0xFFAAAAAA), fontSize = 12.sp)
                }

                Slider(
                    value = thickness,
                    onValueChange = { thickness = it },
                    valueRange = 1f..40f,
                    modifier = Modifier.fillMaxWidth(),
                    colors = SliderDefaults.colors(
                        thumbColor = accent,
                        activeTrackColor = accent,
                    ),
                )

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(4.dp),
                ) {
                    TextButton(onClick = { imagePicker.launch("image/*") }) {
                        Text("Скрин", color = Color(0xFFCCCCCC), fontSize = 13.sp)
                    }
                    TextButton(onClick = {
                        clipboardBitmap(this@PaintActivity)?.let { setBackground(it) }
                            ?: imagePicker.launch("image/*")
                    }) {
                        Text("Вставить", color = Color(0xFFCCCCCC), fontSize = 13.sp)
                    }
                    TextButton(onClick = { undoAction() }) {
                        Text("Undo", color = Color(0xFFCCCCCC), fontSize = 13.sp)
                    }
                    TextButton(onClick = { redoAction() }) {
                        Text("Redo", color = Color(0xFFCCCCCC), fontSize = 13.sp)
                    }
                    TextButton(onClick = { clearCanvas() }) {
                        Text("Очистить", color = Color(0xFFCCCCCC), fontSize = 13.sp)
                    }
                }

                Spacer(Modifier = Modifier.height(6.dp))

                Canvas(
                    modifier = Modifier
                        .fillMaxWidth()
                        .weight(1f)
                        .background(Color.White, RoundedCornerShape(8.dp))
                        .border(1.dp, Color(0xFF555555), RoundedCornerShape(8.dp))
                        .onSizeChanged {
                            canvasSize = it
                            ensureBaseSize(it)
                            frame++
                        }
                        .pointerInput(tool, color, thickness) {
                            if (tool == Tool.Fill) {
                                detectTapGestures { offset -> doFill(offset.x, offset.y) }
                                return@pointerInput
                            }
                            detectDragGestures(
                                onDragStart = { offset ->
                                    start = offset
                                    when (tool) {
                                        Tool.Pen, Tool.Eraser -> {
                                            val path = Path().apply { moveTo(offset.x, offset.y) }
                                            currentPath = DrawOp.Freehand(path, drawColor(), penWidth())
                                        }
                                        else -> preview = null
                                    }
                                    frame++
                                },
                                onDrag = { change, _ ->
                                    change.consume()
                                    val s = start ?: return@detectDragGestures
                                    val end = change.position
                                    when (tool) {
                                        Tool.Pen, Tool.Eraser -> {
                                            currentPath?.path?.lineTo(end.x, end.y)
                                            frame++
                                        }
                                        Tool.Line -> {
                                            preview = DrawOp.LineOp(s, end, color, penWidth())
                                            frame++
                                        }
                                        Tool.Rect -> {
                                            preview = DrawOp.RectOp(s, end, color, penWidth())
                                            frame++
                                        }
                                        Tool.Oval -> {
                                            preview = DrawOp.OvalOp(s, end, color, penWidth())
                                            frame++
                                        }
                                        Tool.Fill -> Unit
                                    }
                                },
                                onDragEnd = {
                                    when (tool) {
                                        Tool.Pen, Tool.Eraser -> {
                                            currentPath?.let { pushOp(it) }
                                            currentPath = null
                                        }
                                        Tool.Line, Tool.Rect, Tool.Oval -> {
                                            preview?.let { pushOp(it) }
                                            preview = null
                                        }
                                        Tool.Fill -> Unit
                                    }
                                    start = null
                                    frame++
                                },
                                onDragCancel = {
                                    currentPath = null
                                    preview = null
                                    start = null
                                    frame++
                                },
                            )
                        },
                ) {
                    @Suppress("UNUSED_EXPRESSION")
                    frame
                    val w = size.width.toInt().coerceAtLeast(1)
                    val h = size.height.toInt().coerceAtLeast(1)
                    val bg = if (baseBmp.width == w && baseBmp.height == h) {
                        baseBmp
                    } else {
                        Bitmap.createScaledBitmap(baseBmp, w, h, true)
                    }
                    drawImage(
                        image = bg.asImageBitmap(),
                        dstOffset = IntOffset.Zero,
                        dstSize = IntSize(w, h),
                    )
                    fun stroke(opColor: Color, width: Float) = Stroke(
                        width = width,
                        cap = StrokeCap.Round,
                        join = StrokeJoin.Round,
                    )
                    (ops + listOfNotNull(preview, currentPath)).forEach { op ->
                        when (op) {
                            is DrawOp.Freehand -> drawPath(op.path, op.color, style = stroke(op.color, op.width))
                            is DrawOp.LineOp -> drawLine(op.color, op.a, op.b, strokeWidth = op.width, cap = StrokeCap.Round)
                            is DrawOp.RectOp -> drawRect(
                                color = op.color,
                                topLeft = Offset(min(op.a.x, op.b.x), min(op.a.y, op.b.y)),
                                size = Size(
                                    abs(op.b.x - op.a.x),
                                    abs(op.b.y - op.a.y),
                                ),
                                style = stroke(op.color, op.width),
                            )
                            is DrawOp.OvalOp -> drawOval(
                                color = op.color,
                                topLeft = Offset(min(op.a.x, op.b.x), min(op.a.y, op.b.y)),
                                size = Size(
                                    abs(op.b.x - op.a.x),
                                    abs(op.b.y - op.a.y),
                                ),
                                style = stroke(op.color, op.width),
                            )
                        }
                    }
                }

                Text(
                    "Пустой холст · Скрин/Вставить = фон из галереи или буфера",
                    color = Color(0xFF666666),
                    fontSize = 11.sp,
                    modifier = Modifier.padding(top = 6.dp),
                )

                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(top = 8.dp),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    TextButton(onClick = { finish() }, modifier = Modifier.weight(1f)) {
                        Text("Отмена", color = Color(0xFF888888))
                    }
                    Button(
                        onClick = {
                            val w = canvasSize.width.coerceAtLeast(1)
                            val h = canvasSize.height.coerceAtLeast(1)
                            DrawingHolder.bitmap = renderFlat(w, h)
                            setResult(RESULT_OK)
                            finish()
                        },
                        modifier = Modifier.weight(1f),
                        colors = ButtonDefaults.buttonColors(containerColor = accent),
                    ) {
                        Text("Вставить в заметку")
                    }
                }
            }
        }
    }
}

private fun fitBitmap(src: Bitmap, tw: Int, th: Int): Bitmap {
    val out = Bitmap.createBitmap(tw, th, Bitmap.Config.ARGB_8888)
    val canvas = AndroidCanvas(out)
    canvas.drawColor(AndroidColor.WHITE)
    val scale = min(tw.toFloat() / src.width, th.toFloat() / src.height)
    val nw = max(1, (src.width * scale).toInt())
    val nh = max(1, (src.height * scale).toInt())
    val scaled = Bitmap.createScaledBitmap(src, nw, nh, true)
    canvas.drawBitmap(scaled, ((tw - nw) / 2f), ((th - nh) / 2f), null)
    return out
}

private fun decodeBitmap(context: Context, uri: Uri): Bitmap? =
    try {
        context.contentResolver.openInputStream(uri)?.use { BitmapFactory.decodeStream(it) }
    } catch (_: Exception) {
        null
    }

private fun clipboardBitmap(context: Context): Bitmap? {
    val cm = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
    val clip = cm.primaryClip ?: return null
    if (clip.itemCount == 0) return null
    val item = clip.getItemAt(0)
    val uri = item.uri
    if (uri != null) return decodeBitmap(context, uri)
    // Some keyboards put HTML/text only — no bitmap
    return null
}

private fun floodFillBitmap(bmp: Bitmap, x: Int, y: Int, newColor: Int, tol: Int) {
    val w = bmp.width
    val h = bmp.height
    if (x !in 0 until w || y !in 0 until h) return
    val pixels = IntArray(w * h)
    bmp.getPixels(pixels, 0, w, 0, 0, w, h)
    val target = pixels[y * w + x]
    if (colorNear(target, newColor, 0)) return

    fun near(c: Int) = colorNear(c, target, tol)

    val stack = ArrayDeque<Int>()
    stack.add(y * w + x)
    while (stack.isNotEmpty()) {
        val i = stack.removeLast()
        if (i < 0 || i >= pixels.size) continue
        if (!near(pixels[i])) continue
        pixels[i] = newColor
        val cx = i % w
        val cy = i / w
        if (cx + 1 < w) stack.add(i + 1)
        if (cx - 1 >= 0) stack.add(i - 1)
        if (cy + 1 < h) stack.add(i + w)
        if (cy - 1 >= 0) stack.add(i - w)
    }
    bmp.setPixels(pixels, 0, w, 0, 0, w, h)
}

private fun colorNear(a: Int, b: Int, tol: Int): Boolean {
    val ar = AndroidColor.red(a)
    val ag = AndroidColor.green(a)
    val ab = AndroidColor.blue(a)
    val br = AndroidColor.red(b)
    val bg = AndroidColor.green(b)
    val bb = AndroidColor.blue(b)
    return abs(ar - br) <= tol &&
        abs(ag - bg) <= tol &&
        abs(ab - bb) <= tol
}

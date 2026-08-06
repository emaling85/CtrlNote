package app.ctrlnote

import android.content.Context
import android.graphics.Bitmap
import android.net.Uri
import androidx.documentfile.provider.DocumentFile
import java.io.IOException
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * Сохранение заметки в папку vault на Android (через Storage Access Framework).
 * Пишет .md файл и PNG-рисунки рядом с ним.
 */
object NoteWriter {
    /**
     * Сохраняет текст и рисунки в vault.
     * @return имя созданного markdown-файла
     */
    fun saveNote(
        context: Context,
        treeUri: Uri,
        body: String,
        drawings: List<Bitmap> = emptyList(),
    ): String {
        val root = DocumentFile.fromTreeUri(context, treeUri)
            ?: throw IOException("Папка vault недоступна")
        if (!root.canWrite()) throw IOException("Нет прав на запись в vault")

        val stamp = SimpleDateFormat("yyyy-MM-dd HH-mm", Locale.US).format(Date())
        val firstLine = body.lineSequence()
            .map { it.trim() }
            .firstOrNull { it.isNotEmpty() && !it.startsWith("![[") }
            ?.take(60)
            ?.replace(Regex("[\\\\/:*?\"<>|]"), "")
            ?.trim()
            .orEmpty()

        val baseName = if (firstLine.isNotEmpty()) "$stamp $firstLine" else stamp
        val mdName = uniqueName(root, "$baseName.md")

        val embeds = StringBuilder()
        drawings.forEachIndexed { index, bitmap ->
            val pngName = uniqueName(
                root,
                if (drawings.size == 1) "Drawing $stamp.png"
                else "Drawing $stamp (${index + 1}).png",
            )
            // Имя без расширения — система часто дописывает его сама по MIME
            val png = root.createFile("image/png", pngName.removeSuffix(".png"))
                ?: throw IOException("Не удалось создать $pngName")
            context.contentResolver.openOutputStream(png.uri)?.use { out ->
                val ok = bitmap.compress(Bitmap.CompressFormat.PNG, 100, out)
                if (!ok) throw IOException("Не удалось сжать PNG")
            } ?: throw IOException("Не удалось записать $pngName")
            embeds.append("![[").append(png.name ?: pngName).append("]]\n")
        }

        val content = buildString {
            if (embeds.isNotEmpty()) append(embeds).append('\n')
            append(body.trim()).append('\n')
        }

        val md = root.createFile("text/markdown", mdName.removeSuffix(".md"))
            ?: root.createFile("text/plain", mdName.removeSuffix(".md"))
            ?: throw IOException("Не удалось создать заметку")
        context.contentResolver.openOutputStream(md.uri)?.use { out ->
            out.write(content.toByteArray(Charsets.UTF_8))
        } ?: throw IOException("Не удалось записать заметку")

        return md.name ?: mdName
    }

    /** Подбирает незанятое имя файла (при конфликте добавляет « (2)» и т.д.). */
    private fun uniqueName(dir: DocumentFile, filename: String): String {
        val safe = filename
            .replace('\\', '/')
            .substringAfterLast('/')
            .replace(Regex("[\\\\/:*?\"<>|]"), "")
            .trim()
            .ifEmpty { "note" }
        if (dir.findFile(safe) == null) return safe
        val dot = safe.lastIndexOf('.')
        val stem = if (dot > 0) safe.substring(0, dot) else safe
        val ext = if (dot > 0) safe.substring(dot) else ""
        var i = 2
        while (true) {
            val candidate = "$stem ($i)$ext"
            if (dir.findFile(candidate) == null) return candidate
            i++
        }
    }
}

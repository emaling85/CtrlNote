package app.ctrlnote

import android.graphics.Bitmap

/**
 * Временное хранилище рисунка между экранами.
 * Так картинка не передаётся через Intent (у него есть лимит размера).
 */
object DrawingHolder {
    @Volatile
    var bitmap: Bitmap? = null
}

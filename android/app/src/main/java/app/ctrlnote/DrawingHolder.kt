package app.ctrlnote

import android.graphics.Bitmap

/** Pass drawing between PaintActivity and CaptureActivity without Intent size limits. */
object DrawingHolder {
    @Volatile
    var bitmap: Bitmap? = null
}

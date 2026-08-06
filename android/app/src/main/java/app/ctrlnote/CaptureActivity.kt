package app.ctrlnote

import android.content.Context
import android.content.Intent
import android.graphics.Bitmap
import android.net.Uri
import android.os.Bundle
import android.view.WindowManager
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.platform.LocalSoftwareKeyboardController
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.documentfile.provider.DocumentFile
import kotlinx.coroutines.delay

class CaptureActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        // Keep capture snappy from quick settings
        window.setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_STATE_VISIBLE)

        val prefs = VaultPrefs(this)

        setContent {
            val accent = Color(0xFF3878FA)
            val bg = Color(0xFF1A1A1A)
            val field = Color(0xFF141414)
            val muted = Color(0xFF888888)

            var text by remember { mutableStateOf("") }
            var vaultLabel by remember {
                mutableStateOf(displayVaultLabel(this, prefs.treeUri))
            }
            var status by remember { mutableStateOf("") }
            val drawings = remember { mutableStateListOf<Bitmap>() }
            val focusRequester = remember { FocusRequester() }
            val keyboard = LocalSoftwareKeyboardController.current
            var askedVault by remember { mutableStateOf(false) }

            fun focusNote() {
                try {
                    focusRequester.requestFocus()
                    keyboard?.show()
                } catch (_: IllegalStateException) {
                    // FocusRequester not attached yet
                }
            }

            val folderPicker = rememberLauncherForActivityResult(
                ActivityResultContracts.OpenDocumentTree(),
            ) { uri: Uri? ->
                if (uri != null) {
                    try {
                        contentResolver.takePersistableUriPermission(
                            uri,
                            Intent.FLAG_GRANT_READ_URI_PERMISSION or
                                Intent.FLAG_GRANT_WRITE_URI_PERMISSION,
                        )
                    } catch (_: SecurityException) {
                        // Some providers don't support persistable; still try to use for session
                    }
                    prefs.treeUri = uri
                    vaultLabel = displayVaultLabel(this@CaptureActivity, uri)
                    status = ""
                    focusNote()
                } else if (prefs.treeUri == null) {
                    status = "Нужна папка vault Obsidian"
                }
            }

            val paintLauncher = rememberLauncherForActivityResult(
                ActivityResultContracts.StartActivityForResult(),
            ) { result ->
                if (result.resultCode == RESULT_OK) {
                    DrawingHolder.bitmap?.let { drawings.add(it) }
                    DrawingHolder.bitmap = null
                }
            }

            LaunchedEffect(Unit) {
                if (!askedVault && prefs.treeUri == null) {
                    askedVault = true
                    delay(250)
                    folderPicker.launch(null)
                } else {
                    delay(200)
                    focusNote()
                    delay(200)
                    focusNote()
                }
            }

            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .background(bg)
                    .padding(horizontal = 16.dp, vertical = 12.dp),
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    TextButton(
                        onClick = { folderPicker.launch(null) },
                        modifier = Modifier.weight(1f),
                    ) {
                        Text(
                            text = "Vault · $vaultLabel",
                            color = Color(0xFFB0B0B0),
                            fontSize = 13.sp,
                            maxLines = 1,
                        )
                    }
                    TextButton(
                        onClick = {
                            paintLauncher.launch(
                                Intent(this@CaptureActivity, PaintActivity::class.java),
                            )
                        },
                    ) {
                        Text("✎", color = Color(0xFFC8C8C8), fontSize = 20.sp)
                    }
                }

                Spacer(Modifier = Modifier.height(4.dp))

                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .weight(1f)
                        .background(field, RoundedCornerShape(10.dp))
                        .padding(14.dp),
                ) {
                    if (text.isEmpty()) {
                        Text("Заметка…", color = Color(0xFF555555), fontSize = 16.sp)
                    }
                    BasicTextField(
                        value = text,
                        onValueChange = { text = it },
                        modifier = Modifier
                            .fillMaxSize()
                            .focusRequester(focusRequester),
                        textStyle = TextStyle(color = Color.White, fontSize = 16.sp, lineHeight = 22.sp),
                        cursorBrush = SolidColor(accent),
                    )
                }

                if (drawings.isNotEmpty()) {
                    Text(
                        "Рисунков: ${drawings.size}",
                        color = muted,
                        fontSize = 12.sp,
                        modifier = Modifier.padding(top = 8.dp),
                    )
                }

                if (status.isNotEmpty()) {
                    Text(
                        status,
                        color = Color(0xFFE07474),
                        fontSize = 12.sp,
                        modifier = Modifier.padding(top = 6.dp),
                    )
                }

                Spacer(modifier = Modifier.height(10.dp))

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    TextButton(
                        onClick = { finish() },
                        modifier = Modifier.weight(1f),
                    ) {
                        Text("Отмена", color = muted)
                    }
                    Button(
                        onClick = {
                            val tree = prefs.treeUri
                            if (tree == null) {
                                status = "Сначала выберите папку vault"
                                folderPicker.launch(null)
                                return@Button
                            }
                            if (text.isBlank() && drawings.isEmpty()) {
                                status = "Пустая заметка"
                                return@Button
                            }
                            try {
                                val name = NoteWriter.saveNote(
                                    this@CaptureActivity,
                                    tree,
                                    text.ifBlank { "Рисунок" },
                                    drawings.toList(),
                                )
                                Toast.makeText(
                                    this@CaptureActivity,
                                    "Сохранено: $name",
                                    Toast.LENGTH_SHORT,
                                ).show()
                                finish()
                            } catch (e: Exception) {
                                status = e.message ?: "Ошибка сохранения"
                            }
                        },
                        modifier = Modifier
                            .weight(1.2f)
                            .height(48.dp),
                        shape = RoundedCornerShape(10.dp),
                        colors = ButtonDefaults.buttonColors(containerColor = accent),
                    ) {
                        Text("Сохранить", fontSize = 16.sp)
                    }
                }
            }
        }
    }

    companion object {
        const val EXTRA_FROM_TILE = "from_tile"

        fun displayVaultLabel(context: Context, uri: Uri?): String {
            if (uri == null) return "выберите vault"
            val name = DocumentFile.fromTreeUri(context, uri)?.name
            if (!name.isNullOrBlank()) return name
            val seg = uri.lastPathSegment ?: return "vault"
            return seg.substringAfterLast(':').substringAfterLast('/')
        }
    }
}

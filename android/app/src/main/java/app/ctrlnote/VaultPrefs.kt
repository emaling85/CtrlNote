package app.ctrlnote

import android.content.Context
import android.content.SharedPreferences
import android.net.Uri

class VaultPrefs(context: Context) {
    private val prefs: SharedPreferences =
        context.getSharedPreferences("ctrlnote", Context.MODE_PRIVATE)

    var treeUri: Uri?
        get() = prefs.getString(KEY_TREE, null)?.let(Uri::parse)
        set(value) {
            prefs.edit().putString(KEY_TREE, value?.toString()).apply()
        }

    companion object {
        private const val KEY_TREE = "vault_tree_uri"
    }
}

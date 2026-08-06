"""
Автотесты безопасности путей (нельзя выйти за пределы vault).
"""

from __future__ import annotations

import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from daily_note import append_to_daily_file
from note_saver import save_note
from setup_wizard import _safe_extractall
from vault_paths import VaultPathError, resolve_under_vault, safe_attachment_name


class VaultContainmentTests(unittest.TestCase):
    def test_resolve_rejects_dotdot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "Vault"
            vault.mkdir()
            with self.assertRaises(VaultPathError):
                resolve_under_vault(vault, "../Outside")

    def test_resolve_rejects_absolute(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "Vault"
            vault.mkdir()
            outside = Path(tmp) / "Outside"
            outside.mkdir()
            with self.assertRaises(VaultPathError):
                resolve_under_vault(vault, str(outside))

    def test_save_note_rejects_escape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "Vault"
            vault.mkdir()
            with self.assertRaises(VaultPathError):
                save_note("x", vault, "../Outside")

    def test_attachment_stays_in_vault(self) -> None:
        from PIL import Image

        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "Vault"
            vault.mkdir()
            outside = Path(tmp) / "Outside"
            outside.mkdir()
            img = Image.new("RGB", (4, 4), color=(0, 255, 0))
            path = save_note(
                "![[../Outside/evil.png]]\nnote",
                vault,
                "",
                attachments=[("../Outside/evil.png", img)],
            )
            self.assertTrue(str(path.resolve()).startswith(str(vault.resolve())))
            self.assertFalse((outside / "evil.png").exists())
            self.assertTrue((vault / "evil.png").exists())

    def test_daily_rejects_escape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "Vault"
            vault.mkdir()
            result = append_to_daily_file(vault, "T", folder="../Outside")
            self.assertIsNone(result)
            self.assertFalse(any(Path(tmp).joinpath("Outside").glob("*.md")))

    def test_safe_attachment_name(self) -> None:
        self.assertEqual(safe_attachment_name("../Outside/evil.png"), "evil.png")
        self.assertEqual(safe_attachment_name("photo..final.png"), "photo..final.png")
        with self.assertRaises(VaultPathError):
            safe_attachment_name("..")

    def test_daily_breaks_hardlink(self) -> None:
        import os

        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "Vault"
            vault.mkdir()
            outside = Path(tmp) / "Outside"
            outside.mkdir()
            outside_file = outside / "exfil.md"
            outside_file.write_text("# outside\n", encoding="utf-8")
            from daily_note import daily_note_name

            link = vault / f"{daily_note_name()}.md"
            os.link(outside_file, link)
            append_to_daily_file(vault, "SecretNote")
            self.assertNotIn("SecretNote", outside_file.read_text(encoding="utf-8"))
            self.assertIn("SecretNote", link.read_text(encoding="utf-8"))

    def test_dpapi_failure_not_plaintext(self) -> None:
        import config as config_mod

        with mock.patch("ctypes.windll.crypt32.CryptProtectData", return_value=0):
            with self.assertRaises(config_mod.SecretStorageError):
                config_mod._dpapi_protect("sk-secret")

    def test_context_create_stays_in_vault(self) -> None:
        from context import resolve_folder

        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "Vault"
            vault.mkdir()
            folder = resolve_folder(vault, title="YouTube - Google Chrome")
            self.assertIsNotNone(folder)
            assert folder is not None
            self.assertTrue((vault / folder).is_dir())
            self.assertFalse(folder.startswith(".."))


class ZipSlipTests(unittest.TestCase):
    def test_safe_extract_rejects_dotdot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "dest"
            dest.mkdir()
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w") as zf:
                zf.writestr("../evil.txt", b"pwn")
                zf.writestr("ok.txt", b"ok")
            buf.seek(0)
            with zipfile.ZipFile(buf, "r") as zf:
                with self.assertRaises(ValueError):
                    _safe_extractall(zf, dest)
            self.assertFalse((Path(tmp) / "evil.txt").exists())


class ApiKeyStorageTests(unittest.TestCase):
    def test_openai_key_not_plain_on_disk(self) -> None:
        import config as config_mod

        with tempfile.TemporaryDirectory() as tmp:
            cfg_path = Path(tmp) / "config.json"
            with mock.patch.object(config_mod, "CONFIG_PATH", cfg_path):
                config_mod.save_config(
                    {
                        **config_mod.DEFAULT_CONFIG,
                        "vault_path": str(tmp),
                        "openai_api_key": "sk-test-secret-key",
                    }
                )
                raw = json.loads(cfg_path.read_text(encoding="utf-8"))
                stored = raw.get("openai_api_key", "")
                self.assertNotEqual(stored, "sk-test-secret-key")
                if config_mod.sys.platform == "win32":
                    self.assertTrue(
                        str(stored).startswith("dpapi:"),
                        msg=f"expected DPAPI blob, got {stored!r}",
                    )
                loaded = config_mod.load_config()
                self.assertEqual(loaded["openai_api_key"], "sk-test-secret-key")


class InstallDestTests(unittest.TestCase):
    def test_normalize_appends_ctrlnote(self) -> None:
        from setup_wizard import APP_NAME, _normalize_install_dest

        with tempfile.TemporaryDirectory() as tmp:
            dest = _normalize_install_dest(Path(tmp))
            self.assertEqual(dest.name, APP_NAME)
            self.assertTrue(str(dest).endswith(APP_NAME))

    def test_normalize_rejects_shallow(self) -> None:
        from setup_wizard import _normalize_install_dest

        with self.assertRaises(ValueError):
            _normalize_install_dest(Path("C:/"))


class FolderLabelTests(unittest.TestCase):
    def test_root_label_not_overwritten_by_same_named_folder(self) -> None:
        from note_saver import list_vault_folders

        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "Vault"
            vault.mkdir()
            (vault / "(корень vault)").mkdir()
            folders = list_vault_folders(vault)
            self.assertIn("", folders)
            self.assertIn("(корень vault)", folders)
            # UI maps colliding name to ./ (корень vault); both keys coexist
            labels = []
            fmap = {}
            for rel in folders:
                if rel == "":
                    label = "(корень vault)"
                elif rel == "(корень vault)":
                    label = "./(корень vault)"
                else:
                    label = rel
                labels.append(label)
                fmap[label] = rel
            self.assertEqual(fmap["(корень vault)"], "")
            self.assertEqual(fmap["./(корень vault)"], "(корень vault)")


if __name__ == "__main__":
    unittest.main()

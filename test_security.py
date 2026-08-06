"""Security tests: vault containment + zip slip rejection + secrets."""

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
        with self.assertRaises(VaultPathError):
            safe_attachment_name("..")

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


if __name__ == "__main__":
    unittest.main()

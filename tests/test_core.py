"""
Автотесты ядра: сохранение заметок, имена файлов, пути vault.
"""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from config import DEFAULT_CONFIG, is_configured, load_config, save_config
from note_saver import build_note_filename, list_vault_folders, sanitize_filename, save_note


class NoteSaverTests(unittest.TestCase):
    def test_sanitize(self) -> None:
        self.assertEqual(sanitize_filename('a/b:c*?"<>|.md'), "abc.md")
        self.assertEqual(sanitize_filename("  hello   world  "), "hello world")

    def test_filename_from_first_line(self) -> None:
        now = datetime(2026, 8, 1, 17, 42)
        name = build_note_filename("Идея для CtrlNote\nтело", now)
        self.assertEqual(name, "2026-08-01 17-42 Идея для CtrlNote.md")

    def test_filename_strips_heading(self) -> None:
        now = datetime(2026, 8, 1, 17, 42)
        name = build_note_filename("# Встреча\nтекст", now)
        self.assertEqual(name, "2026-08-01 17-42 Встреча.md")

    def test_filename_empty(self) -> None:
        now = datetime(2026, 8, 1, 17, 42)
        self.assertEqual(build_note_filename("   \n  ", now), "2026-08-01 17-42.md")

    def test_filename_skips_image_embed(self) -> None:
        now = datetime(2026, 8, 1, 17, 42)
        name = build_note_filename("![[Pasted image.png]]\nИдея", now)
        self.assertEqual(name, "2026-08-01 17-42 Идея.md")
        self.assertEqual(
            build_note_filename("![[Pasted image.png]]\n", now),
            "2026-08-01 17-42.md",
        )

    def test_save_and_list_folders(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            (vault / "Projects" / "Alpha").mkdir(parents=True)
            (vault / ".obsidian").mkdir()
            (vault / "Inbox").mkdir()

            folders = list_vault_folders(vault)
            self.assertIn("", folders)
            self.assertIn("Projects", folders)
            self.assertIn("Projects/Alpha", folders)
            self.assertIn("Inbox", folders)
            self.assertTrue(all(not f.startswith(".") for f in folders if f))

            path = save_note("Заголовок\nтекст заметки", vault, "Projects/Alpha")
            self.assertTrue(path.exists())
            self.assertEqual(path.parent, vault / "Projects" / "Alpha")
            self.assertTrue(path.name.endswith("Заголовок.md"))
            self.assertIn("текст заметки", path.read_text(encoding="utf-8"))

            # Уникальные имена при совпадении
            path2 = save_note("Заголовок\nвторая", vault, "Projects/Alpha")
            self.assertNotEqual(path, path2)
            self.assertTrue(path2.exists())

    def test_save_with_attachment(self) -> None:
        from PIL import Image

        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            img = Image.new("RGB", (8, 8), color=(255, 0, 0))
            content = "![[Pasted image test.png]]\nскрин"
            path = save_note(
                content,
                vault,
                "",
                attachments=[("Pasted image test.png", img)],
            )
            image_path = vault / "Pasted image test.png"
            self.assertTrue(path.exists())
            self.assertTrue(image_path.exists())
            self.assertIn("![[Pasted image test.png]]", path.read_text(encoding="utf-8"))


class HotkeyParseTests(unittest.TestCase):
    def test_parse_ctrl_alt_n(self) -> None:
        from hotkey_win import MOD_ALT, MOD_CONTROL, MOD_NOREPEAT, parse_hotkey

        mods, vk = parse_hotkey("ctrl+alt+n")
        self.assertEqual(vk, ord("N"))
        self.assertEqual(mods & MOD_CONTROL, MOD_CONTROL)
        self.assertEqual(mods & MOD_ALT, MOD_ALT)
        self.assertEqual(mods & MOD_NOREPEAT, MOD_NOREPEAT)


class AutostartTests(unittest.TestCase):
    def test_ps_quote(self) -> None:
        from autostart import _ps_quote

        self.assertEqual(_ps_quote(r"C:\проекты\CtrlNote"), r"'C:\проекты\CtrlNote'")
        self.assertEqual(_ps_quote("O'Brien"), "'O''Brien'")

    def test_resolve_launch_exists(self) -> None:
        from autostart import _resolve_launch

        target, _args, workdir = _resolve_launch()
        self.assertTrue(target.exists(), msg=str(target))
        self.assertTrue(workdir.exists(), msg=str(workdir))


class ConfigTests(unittest.TestCase):
    def test_roundtrip(self) -> None:
        # Use a temp config by monkeypatching path via writing then reading
        from config import CONFIG_PATH

        original = CONFIG_PATH.read_text(encoding="utf-8") if CONFIG_PATH.exists() else None
        try:
            save_config(
                {
                    "vault_path": str(Path.cwd()),
                    "hotkey": "ctrl+alt+n",
                    "last_folder": "Inbox",
                }
            )
            cfg = load_config()
            self.assertEqual(cfg["hotkey"], "ctrl+alt+n")
            self.assertEqual(cfg["last_folder"], "Inbox")
            self.assertTrue(is_configured(cfg))
            self.assertFalse(is_configured({**DEFAULT_CONFIG, "vault_path": ""}))
        finally:
            if original is None:
                if CONFIG_PATH.exists():
                    CONFIG_PATH.unlink()
            else:
                CONFIG_PATH.write_text(original, encoding="utf-8")


if __name__ == "__main__":
    unittest.main()

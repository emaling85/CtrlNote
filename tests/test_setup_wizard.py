"""
Автотесты установщика: переустановка не стирает данные пользователя.
"""

from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

import setup_wizard


class ReinstallTests(unittest.TestCase):
    def test_reinstall_keeps_user_data_and_reads_edition(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = root / "app.zip"
            with zipfile.ZipFile(payload, "w") as zf:
                zf.writestr("CtrlNote.exe", "new exe")
                zf.writestr("_internal/edition.txt", "trader\n")

            dest = root / "apps" / "CtrlNote"
            dest.mkdir(parents=True)
            (dest / "CtrlNote.exe").write_text("old exe")
            (dest / "old_lib.dll").write_text("stale")
            (dest / "config.json").write_text('{"vault_path": "x"}')
            (dest / "templates.json").write_text("[]")
            (dest / "trade_options.json").write_text("{}")
            (dest / "recordings").mkdir()
            (dest / "recordings" / "a.wav").write_text("audio")

            with mock.patch.object(setup_wizard, "_payload_zip", return_value=payload), mock.patch.object(
                setup_wizard, "_close_running_app"
            ):
                exe = setup_wizard.install(dest, desktop=False, start_menu=False, autostart=False)
                self.assertEqual(setup_wizard._payload_edition(), "trader")  # noqa: SLF001

            self.assertEqual(exe.read_text(), "new exe")
            self.assertFalse((dest / "old_lib.dll").exists())
            self.assertEqual((dest / "config.json").read_text(), '{"vault_path": "x"}')
            self.assertTrue((dest / "templates.json").exists())
            self.assertTrue((dest / "trade_options.json").exists())
            self.assertEqual((dest / "recordings" / "a.wav").read_text(), "audio")


if __name__ == "__main__":
    unittest.main()

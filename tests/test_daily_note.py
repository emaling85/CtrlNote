"""
Автотесты связи с ежедневной заметкой Obsidian.
"""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from daily_note import append_daily_link, append_to_daily_file, daily_wikilink


class DailyNoteTests(unittest.TestCase):
    def test_wikilink(self) -> None:
        now = datetime(2026, 8, 1, 12, 0)
        self.assertEqual(daily_wikilink(now=now), "[[2026-08-01]]")

    def test_append_link(self) -> None:
        now = datetime(2026, 8, 1, 12, 0)
        text = append_daily_link("hello", now=now)
        self.assertIn("[[2026-08-01]]", text)
        self.assertTrue(text.startswith("hello"))

    def test_append_file(self) -> None:
        now = datetime(2026, 8, 1, 12, 0)
        with tempfile.TemporaryDirectory() as tmp:
            path = append_to_daily_file(tmp, "My note", folder="Daily", now=now)
            self.assertIsNotNone(path)
            assert path is not None
            self.assertTrue(path.exists())
            body = path.read_text(encoding="utf-8")
            self.assertIn("[[My note]]", body)


if __name__ == "__main__":
    unittest.main()

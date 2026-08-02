"""Tests for active-window → vault folder matching / creation."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from context import extract_context_name, match_vault_folder, resolve_folder, suggest_folder


class ContextTests(unittest.TestCase):
    def test_youtube_chrome(self) -> None:
        self.assertEqual(
            extract_context_name("Cool talk - YouTube - Google Chrome"),
            "YouTube",
        )

    def test_youtube_edge(self) -> None:
        self.assertEqual(
            extract_context_name("Something - YouTube - Microsoft Edge"),
            "YouTube",
        )

    def test_cursor_project(self) -> None:
        self.assertEqual(
            extract_context_name("main.py - CtrlNote - Cursor"),
            "CtrlNote",
        )

    def test_rejects_long_page_title(self) -> None:
        self.assertIsNone(
            extract_context_name(
                "простой сайт или бот для бизнеса - Google Chrome"
            )
        )

    def test_telegram(self) -> None:
        self.assertEqual(
            extract_context_name("Saved Messages - Telegram"),
            "Telegram",
        )

    def test_match_basename(self) -> None:
        folders = ["", "Inbox", "Projects/CtrlNote", "Projects/Other"]
        self.assertEqual(match_vault_folder(["CtrlNote"], folders), "Projects/CtrlNote")

    def test_suggest_ignores_own_window(self) -> None:
        folders = ["", "Projects/CtrlNote"]
        self.assertIsNone(suggest_folder(folders, title="CtrlNote"))

    def test_resolve_creates_folder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            (vault / "Inbox").mkdir()
            created = resolve_folder(
                vault,
                title="Clip - YouTube - Google Chrome",
                create=True,
            )
            self.assertEqual(created, "YouTube")
            self.assertTrue((vault / "YouTube").is_dir())

    def test_resolve_reuses_existing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            (vault / "YouTube").mkdir()
            got = resolve_folder(
                vault,
                title="Clip - YouTube - Google Chrome",
                create=True,
            )
            self.assertEqual(got, "YouTube")


if __name__ == "__main__":
    unittest.main()

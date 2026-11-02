"""
Автотесты редакций: обычный CtrlNote и CtrlNote Trader.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import edition


class EditionTests(unittest.TestCase):
    def check(self, marker: str | None, frozen: bool) -> str:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            if marker is not None:
                (root / "edition.txt").write_text(marker, encoding="utf-8")
            with mock.patch.object(edition, "resource_root", return_value=root), mock.patch.object(
                edition.sys, "frozen", frozen, create=True
            ):
                return edition.edition()

    def test_marker_wins(self) -> None:
        self.assertEqual(self.check("trader\n", frozen=True), edition.TRADER)
        self.assertEqual(self.check("standard", frozen=False), edition.STANDARD)

    def test_frozen_without_marker_is_standard(self) -> None:
        self.assertEqual(self.check(None, frozen=True), edition.STANDARD)

    def test_source_run_has_everything(self) -> None:
        self.assertEqual(self.check(None, frozen=False), edition.TRADER)


if __name__ == "__main__":
    unittest.main()

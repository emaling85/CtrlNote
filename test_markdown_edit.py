"""
Автотесты горячих клавиш markdown в поле заметки.
"""

from __future__ import annotations

import unittest

from markdown_edit import _next_marker


class NextMarkerTests(unittest.TestCase):
    def test_bullet(self) -> None:
        self.assertEqual(_next_marker("-"), "-")
        self.assertEqual(_next_marker("*"), "*")

    def test_numbered_dot(self) -> None:
        self.assertEqual(_next_marker("1."), "2.")
        self.assertEqual(_next_marker("9."), "10.")

    def test_numbered_paren(self) -> None:
        self.assertEqual(_next_marker("3)"), "4)")


class ToggleWrapLogicTests(unittest.TestCase):
    """Простые проверки строк, как у toggle_wrap (жирный/курсив)."""

    def test_wrap_unwrap(self) -> None:
        marker = "**"
        selected = "hello"
        wrapped = f"{marker}{selected}{marker}"
        self.assertTrue(wrapped.startswith(marker) and wrapped.endswith(marker))
        unwrapped = wrapped[len(marker) : -len(marker)]
        self.assertEqual(unwrapped, "hello")


if __name__ == "__main__":
    unittest.main()

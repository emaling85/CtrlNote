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
    def test_visual_bold_exports_markdown(self) -> None:
        import tkinter as tk

        from markdown_edit import setup_rich_tags, toggle_style, widget_to_markdown

        root = tk.Tk()
        root.withdraw()
        text = tk.Text(root)
        setup_rich_tags(text)
        text.insert("1.0", "hello")
        text.tag_add("sel", "1.0", "1.5")
        toggle_style(text, "bold")
        self.assertEqual(text.get("1.0", "end-1c"), "hello")
        self.assertIn("bold", text.tag_names("1.0"))
        self.assertEqual(widget_to_markdown(text), "**hello**")
        root.destroy()


if __name__ == "__main__":
    unittest.main()

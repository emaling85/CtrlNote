"""Markdown editing helpers for the capture textbox (Obsidian-like shortcuts)."""

from __future__ import annotations

import re
import tkinter as tk
from typing import Any

# bullet: - * +   numbered: 1. 2)   space after marker optional
_LIST_RE = re.compile(r"^(\s*)([-*+]|\d+[.)])(\s*)(.*)$")

# Windows virtual-key codes (layout-independent)
_VK_B = 66
_VK_I = 73


def _inner_text(widget: Any) -> tk.Text:
    """CTkTextbox wraps a real tk.Text as _textbox."""
    inner = getattr(widget, "_textbox", None)
    return inner if inner is not None else widget


def toggle_wrap(widget: Any, marker: str) -> None:
    """Wrap selection (or word/cursor) with marker, or unwrap if already wrapped."""
    text = _inner_text(widget)
    try:
        start = text.index("sel.first")
        end = text.index("sel.last")
        selected = text.get(start, end)
    except tk.TclError:
        try:
            start = text.index("insert wordstart")
            end = text.index("insert wordend")
            selected = text.get(start, end)
            if not selected.strip():
                raise tk.TclError
        except tk.TclError:
            text.insert("insert", f"{marker}{marker}")
            text.mark_set("insert", f"insert-{len(marker)}c")
            return

    if (
        selected.startswith(marker)
        and selected.endswith(marker)
        and len(selected) >= 2 * len(marker)
    ):
        replacement = selected[len(marker) : -len(marker)]
    else:
        replacement = f"{marker}{selected}{marker}"

    text.delete(start, end)
    text.insert(start, replacement)
    text.tag_remove("sel", "1.0", "end")
    text.mark_set("insert", f"{start}+{len(replacement)}c")
    text.see("insert")


def continue_list_on_return(widget: Any) -> str | None:
    """If current line is a list item, continue it on Enter."""
    text = _inner_text(widget)
    line_start = text.index("insert linestart")
    line_end = text.index("insert lineend")
    # Allow continue when cursor is at EOL or only trailing spaces after it
    after = text.get("insert", line_end)
    if after.strip():
        return None

    line = text.get(line_start, line_end).rstrip()
    match = _LIST_RE.match(line)
    if not match:
        return None

    indent, marker, space, body = match.groups()
    gap = space if space else " "

    if not body.strip():
        text.delete(line_start, line_end)
        return "break"

    next_marker = _next_marker(marker)
    # Replace any trailing spaces after cursor, then new list line
    if after:
        text.delete("insert", line_end)
    text.insert("insert", f"\n{indent}{next_marker}{gap}")
    return "break"


def _next_marker(marker: str) -> str:
    if marker in {"-", "*", "+"}:
        return marker
    num_match = re.match(r"(\d+)", marker)
    assert num_match is not None
    num = int(num_match.group(1))
    suffix = marker[len(str(num)) :]
    return f"{num + 1}{suffix}"


def bind_markdown_shortcuts(root: Any, textbox: Any) -> None:
    """Bind Ctrl+B/I (any keyboard layout) and list-continue on Enter.

    Bind only once via CTkTextbox.bind (it forwards to the real Text).
    """

    def on_bold(_event: tk.Event | None = None) -> str:
        toggle_wrap(textbox, "**")
        return "break"

    def on_italic(_event: tk.Event | None = None) -> str:
        toggle_wrap(textbox, "*")
        return "break"

    def on_ctrl_key(event: tk.Event) -> str | None:
        # Layout-independent: physical B / I keys
        if event.keycode == _VK_B:
            return on_bold(event)
        if event.keycode == _VK_I:
            return on_italic(event)
        return None

    def on_return(_event: tk.Event | None = None) -> str | None:
        return continue_list_on_return(textbox)

    # CTkTextbox.bind → inner Text (do NOT also bind inner, or handlers run twice
    # and bold wraps then unwraps = looks broken)
    textbox.bind("<Control-KeyPress>", on_ctrl_key)
    textbox.bind("<Control-b>", on_bold)
    textbox.bind("<Control-B>", on_bold)
    textbox.bind("<Control-i>", on_italic)
    textbox.bind("<Control-I>", on_italic)
    textbox.bind("<Return>", on_return)
    textbox.bind("<KP_Enter>", on_return)

    # Root fallback when focus is inside the textbox (Russian layout / focus quirks)
    def on_root_ctrl(event: tk.Event) -> str | None:
        focus = root.focus_get()
        inner = getattr(textbox, "_textbox", None)
        if focus is not textbox and focus is not inner:
            return None
        return on_ctrl_key(event)

    root.bind("<Control-KeyPress>", on_root_ctrl, add="+")

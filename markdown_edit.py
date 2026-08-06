"""
Markdown editing shortcuts with visual bold/italic (no visible ** / *).

Ctrl+B / Ctrl+I toggle font weight/slant tags. On save we export real markdown.
"""

from __future__ import annotations

import re
import tkinter as tk
from typing import Any

_LIST_RE = re.compile(r"^(\s*)([-*+]|\d+[.)])(\s*)(.*)$")
_VK_B = 66
_VK_I = 73
_MD_BOLD = re.compile(r"\*\*(.+?)\*\*")
_MD_ITALIC = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)")


def _inner_text(widget: Any) -> tk.Text:
    inner = getattr(widget, "_textbox", None)
    return inner if inner is not None else widget


def setup_rich_tags(widget: Any) -> None:
    """Configure bold/italic display tags on the underlying Text widget."""
    text = _inner_text(widget)
    base = text.cget("font")
    try:
        # Prefer tuple fonts for reliable bold/italic variants
        family = "Segoe UI"
        size = 14
        if isinstance(base, str) and base:
            # e.g. "{Segoe UI} 14" or "SegoeUI 14"
            parts = text.tk.splitlist(base)
            if parts:
                family = parts[0]
            if len(parts) > 1:
                try:
                    size = int(float(parts[1]))
                except ValueError:
                    pass
        text.tag_configure("bold", font=(family, size, "bold"))
        text.tag_configure("italic", font=(family, size, "italic"))
        text.tag_configure("bold_italic", font=(family, size, "bold italic"))
    except tk.TclError:
        text.tag_configure("bold", font="TkDefaultFont 14 bold")
        text.tag_configure("italic", font="TkDefaultFont 14 italic")


def _selection_range(text: tk.Text) -> tuple[str, str] | None:
    try:
        return text.index("sel.first"), text.index("sel.last")
    except tk.TclError:
        try:
            start = text.index("insert wordstart")
            end = text.index("insert wordend")
            if text.get(start, end).strip():
                return start, end
        except tk.TclError:
            return None
    return None


def _refresh_combined_tags(text: tk.Text, start: str, end: str) -> None:
    """Ensure bold+italic overlap uses bold_italic font."""
    text.tag_remove("bold_italic", start, end)
    # Walk the range in small steps
    index = start
    while text.compare(index, "<", end):
        nxt = text.index(f"{index}+1c")
        tags = set(text.tag_names(index))
        if "bold" in tags and "italic" in tags:
            text.tag_add("bold_italic", index, nxt)
        index = nxt


def toggle_style(widget: Any, style: str) -> None:
    """Toggle visual bold or italic on the selection (no markdown markers)."""
    text = _inner_text(widget)
    setup_rich_tags(widget)
    rng = _selection_range(text)
    if rng is None:
        # Nothing to style — insert a space and style it so typing continues bold
        text.insert("insert", " ")
        start = text.index("insert-1c")
        end = text.index("insert")
        text.tag_add(style, start, end)
        text.mark_set("insert", end)
        text.tag_remove("sel", "1.0", "end")
        return

    start, end = rng
    # If every character already has the style, remove; else add
    index = start
    all_have = True
    while text.compare(index, "<", end):
        if style not in text.tag_names(index):
            all_have = False
            break
        index = text.index(f"{index}+1c")

    if all_have:
        text.tag_remove(style, start, end)
    else:
        text.tag_add(style, start, end)
    _refresh_combined_tags(text, start, end)
    text.tag_remove("sel", "1.0", "end")
    text.mark_set("insert", end)
    text.see("insert")


def toggle_wrap(widget: Any, marker: str) -> None:
    """Back-compat: ** → bold tag, * → italic tag."""
    if marker == "**":
        toggle_style(widget, "bold")
    else:
        toggle_style(widget, "italic")


def widget_to_markdown(widget: Any) -> str:
    """Export widget content with ** / * for styled spans (for Obsidian)."""
    text = _inner_text(widget)
    end = text.index("end-1c")
    if text.compare("1.0", ">=", end):
        return ""

    out: list[str] = []
    index = "1.0"
    bold = italic = False

    while text.compare(index, "<", end):
        ch = text.get(index)
        tags = set(text.tag_names(index))
        want_bold = "bold" in tags or "bold_italic" in tags
        want_italic = "italic" in tags or "bold_italic" in tags

        # Close markers before opening changes when leaving a style
        if bold and not want_bold:
            out.append("**")
            bold = False
        if italic and not want_italic:
            out.append("*")
            italic = False

        if want_italic and not italic:
            out.append("*")
            italic = True
        if want_bold and not bold:
            out.append("**")
            bold = True

        out.append(ch)
        index = text.index(f"{index}+1c")

    if bold:
        out.append("**")
    if italic:
        out.append("*")
    return "".join(out)


def set_widget_markdown(widget: Any, md: str) -> None:
    """Load markdown into the widget, showing bold/italic without markers."""
    text = _inner_text(widget)
    setup_rich_tags(widget)
    text.delete("1.0", "end")
    if not md:
        return

    # Simple parse: split by ** and * (non-greedy sequential)
    # Strategy: convert to list of (segment, bold, italic)
    pos = 0
    bold = italic = False
    # Tokenize with regex finding ** or *
    token_re = re.compile(r"\*\*|\*")
    chunks: list[tuple[str, bool, bool]] = []
    for m in token_re.finditer(md):
        if m.start() > pos:
            chunks.append((md[pos : m.start()], bold, italic))
        tok = m.group(0)
        if tok == "**":
            bold = not bold
        else:
            italic = not italic
        pos = m.end()
    if pos < len(md):
        chunks.append((md[pos:], bold, italic))

    for segment, is_bold, is_italic in chunks:
        if not segment:
            continue
        start = text.index("insert")
        text.insert("insert", segment)
        end = text.index("insert")
        if is_bold and is_italic:
            text.tag_add("bold", start, end)
            text.tag_add("italic", start, end)
            text.tag_add("bold_italic", start, end)
        elif is_bold:
            text.tag_add("bold", start, end)
        elif is_italic:
            text.tag_add("italic", start, end)


def continue_list_on_return(widget: Any) -> str | None:
    text = _inner_text(widget)
    line_start = text.index("insert linestart")
    line_end = text.index("insert lineend")
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
    setup_rich_tags(textbox)

    def on_bold(_event: tk.Event | None = None) -> str:
        toggle_style(textbox, "bold")
        return "break"

    def on_italic(_event: tk.Event | None = None) -> str:
        toggle_style(textbox, "italic")
        return "break"

    def on_ctrl_key(event: tk.Event) -> str | None:
        if event.keycode == _VK_B:
            return on_bold(event)
        if event.keycode == _VK_I:
            return on_italic(event)
        return None

    def on_return(_event: tk.Event | None = None) -> str | None:
        return continue_list_on_return(textbox)

    textbox.bind("<Control-KeyPress>", on_ctrl_key)
    textbox.bind("<Control-b>", on_bold)
    textbox.bind("<Control-B>", on_bold)
    textbox.bind("<Control-i>", on_italic)
    textbox.bind("<Control-I>", on_italic)
    textbox.bind("<Return>", on_return)
    textbox.bind("<KP_Enter>", on_return)

    def on_root_ctrl(event: tk.Event) -> str | None:
        focus = root.focus_get()
        inner = getattr(textbox, "_textbox", None)
        if focus is not textbox and focus is not inner:
            return None
        return on_ctrl_key(event)

    root.bind("<Control-KeyPress>", on_root_ctrl, add="+")

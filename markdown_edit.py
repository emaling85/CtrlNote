"""
Горячие клавиши редактирования markdown в поле заметки (как в Obsidian).

Ctrl+B — жирный, Ctrl+I — курсив, Enter — продолжение списка.
"""

from __future__ import annotations

import re
import tkinter as tk
from typing import Any

# Распознаём строки списка: - пункт, * пункт, 1. пункт и т.п.
_LIST_RE = re.compile(r"^(\s*)([-*+]|\d+[.)])(\s*)(.*)$")

# Физические коды клавиш B и I (не зависят от русской/английской раскладки)
_VK_B = 66
_VK_I = 73


def _inner_text(widget: Any) -> tk.Text:
    """Достаёт настоящий виджет текста из обёртки CustomTkinter."""
    inner = getattr(widget, "_textbox", None)
    return inner if inner is not None else widget


def toggle_wrap(widget: Any, marker: str) -> None:
    """
    Оборачивает выделенный текст маркерами (** или *) или снимает их, если уже есть.

    Если ничего не выделено — берёт слово под курсором или вставляет пустые маркеры.
    """
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
            # Нет выделения — ставим **|** и курсор посередине
            text.insert("insert", f"{marker}{marker}")
            text.mark_set("insert", f"insert-{len(marker)}c")
            return

    # Уже обёрнуто — снимаем; иначе — оборачиваем
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
    """Если текущая строка — пункт списка, по Enter создаёт следующий пункт."""
    text = _inner_text(widget)
    line_start = text.index("insert linestart")
    line_end = text.index("insert lineend")
    # Продолжаем список только если курсор в конце строки (или после пробелов)
    after = text.get("insert", line_end)
    if after.strip():
        return None

    line = text.get(line_start, line_end).rstrip()
    match = _LIST_RE.match(line)
    if not match:
        return None

    indent, marker, space, body = match.groups()
    gap = space if space else " "

    # Пустой пункт списка — Enter «закрывает» список (удаляет маркер)
    if not body.strip():
        text.delete(line_start, line_end)
        return "break"

    next_marker = _next_marker(marker)
    if after:
        text.delete("insert", line_end)
    text.insert("insert", f"\n{indent}{next_marker}{gap}")
    return "break"


def _next_marker(marker: str) -> str:
    """Для «-» оставляет «-»; для «1.» даёт «2.» и т.д."""
    if marker in {"-", "*", "+"}:
        return marker
    num_match = re.match(r"(\d+)", marker)
    assert num_match is not None
    num = int(num_match.group(1))
    suffix = marker[len(str(num)) :]
    return f"{num + 1}{suffix}"


def bind_markdown_shortcuts(root: Any, textbox: Any) -> None:
    """
    Вешает Ctrl+B / Ctrl+I и продолжение списка на Enter.

    Привязка один раз через CTkTextbox.bind (иначе жирный «мигает» туда-сюда).
    """

    def on_bold(_event: tk.Event | None = None) -> str:
        toggle_wrap(textbox, "**")
        return "break"

    def on_italic(_event: tk.Event | None = None) -> str:
        toggle_wrap(textbox, "*")
        return "break"

    def on_ctrl_key(event: tk.Event) -> str | None:
        # По физическим клавишам — работает и на русской раскладке
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

    # Запасной вариант через корневое окно (фокус / раскладка)
    def on_root_ctrl(event: tk.Event) -> str | None:
        focus = root.focus_get()
        inner = getattr(textbox, "_textbox", None)
        if focus is not textbox and focus is not inner:
            return None
        return on_ctrl_key(event)

    root.bind("<Control-KeyPress>", on_root_ctrl, add="+")

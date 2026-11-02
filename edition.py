"""
Редакция сборки: обычный CtrlNote или CtrlNote Trader (с журналом сделок).

Код один, а сборщик (build_exe.py --edition ...) кладёт в exe файл edition.txt.
При запуске из исходников включено всё — так удобнее разрабатывать.
"""

from __future__ import annotations

import sys

from paths import resource_root

STANDARD = "standard"
TRADER = "trader"


def edition() -> str:
    """Какая редакция запущена: 'standard' или 'trader'."""
    marker = resource_root() / "edition.txt"
    try:
        value = marker.read_text(encoding="utf-8").strip().lower()
    except OSError:
        value = ""
    if value in {STANDARD, TRADER}:
        return value
    # Собранный exe без метки — считаем обычной версией
    return STANDARD if getattr(sys, "frozen", False) else TRADER


def is_trader() -> bool:
    return edition() == TRADER


def app_name() -> str:
    return "CtrlNote Trader" if is_trader() else "CtrlNote"

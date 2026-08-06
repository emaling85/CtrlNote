"""
Пути к файлам программы и к картинкам/ресурсам.

Нужен и при разработке (папка проекта), и когда приложение собрано в .exe.
"""

from __future__ import annotations

import sys
from pathlib import Path


def app_root() -> Path:
    """Папка, где «живёт» приложение (рядом с .exe или с исходниками)."""
    # PyInstaller помечает собранный exe флагом frozen
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def resource_root() -> Path:
    """
    Откуда брать встроенные ресурсы (иконки и т.п.).

    В .exe они лежат во временной папке _MEIPASS; при разработке — в проекте.
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent


def asset_path(*parts: str) -> Path:
    """Полный путь к файлу внутри папки assets (например, иконке)."""
    return resource_root().joinpath("assets", *parts)

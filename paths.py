"""Resolve bundled asset paths (dev + frozen exe)."""

from __future__ import annotations

import sys
from pathlib import Path


def app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def resource_root() -> Path:
    """Where bundled read-only assets live (PyInstaller _MEIPASS or project dir)."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent


def asset_path(*parts: str) -> Path:
    return resource_root().joinpath("assets", *parts)

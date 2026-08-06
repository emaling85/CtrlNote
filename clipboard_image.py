"""Clipboard image helpers (Windows-friendly)."""

from __future__ import annotations

import io
import struct
from pathlib import Path

from PIL import Image, ImageGrab


def grab_clipboard_image() -> Image.Image | None:
    """Return an RGB image from the clipboard, or None."""
    clipped = ImageGrab.grabclipboard()
    if isinstance(clipped, Image.Image):
        return clipped.convert("RGB")
    if isinstance(clipped, list):
        for item in clipped:
            try:
                return Image.open(item).convert("RGB")
            except Exception:  # noqa: BLE001
                continue

    # Win+Shift+S / many apps put PNG or DIB that Pillow sometimes misses
    png = _clipboard_format_bytes("PNG")
    if png:
        try:
            return Image.open(io.BytesIO(png)).convert("RGB")
        except Exception:  # noqa: BLE001
            pass

    dib = _clipboard_dib()
    if dib is not None:
        return dib

    return None


def _clipboard_format_bytes(format_name: str) -> bytes | None:
    import sys

    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        fmt = user32.RegisterClipboardFormatW(format_name)
        if not fmt:
            return None
        if not user32.OpenClipboard(None):
            return None
        try:
            if not user32.IsClipboardFormatAvailable(fmt):
                return None
            handle = user32.GetClipboardData(fmt)
            if not handle:
                return None
            ptr = kernel32.GlobalLock(handle)
            if not ptr:
                return None
            try:
                size = kernel32.GlobalSize(handle)
                return ctypes.string_at(ptr, size)
            finally:
                kernel32.GlobalUnlock(handle)
        finally:
            user32.CloseClipboard()
    except Exception:  # noqa: BLE001
        return None


def _clipboard_dib() -> Image.Image | None:
    import sys

    if sys.platform != "win32":
        return None
    try:
        import ctypes

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        CF_DIB = 8
        if not user32.OpenClipboard(None):
            return None
        try:
            if not user32.IsClipboardFormatAvailable(CF_DIB):
                return None
            handle = user32.GetClipboardData(CF_DIB)
            if not handle:
                return None
            ptr = kernel32.GlobalLock(handle)
            if not ptr:
                return None
            try:
                size = int(kernel32.GlobalSize(handle))
                data = ctypes.string_at(ptr, size)
            finally:
                kernel32.GlobalUnlock(handle)
        finally:
            user32.CloseClipboard()

        if len(data) < 40:
            return None
        header_size = struct.unpack_from("<I", data, 0)[0]
        if header_size < 40:
            return None
        # BITMAPFILEHEADER + DIB
        file_size = 14 + len(data)
        bmp = (
            b"BM"
            + struct.pack("<IHHI", file_size, 0, 0, 14 + header_size)
            + data
        )
        return Image.open(io.BytesIO(bmp)).convert("RGB")
    except Exception:  # noqa: BLE001
        return None

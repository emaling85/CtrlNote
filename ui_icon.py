"""Apply CtrlNote window icons (title bar / taskbar) consistently."""

from __future__ import annotations

from typing import Any

from paths import asset_path

_photo_refs: list[Any] = []


def apply_window_icon(window: Any) -> None:
    """Set .ico + PNG iconphoto on a Tk / CTk window or toplevel."""
    ico = asset_path("icon.ico")
    png = asset_path("icon.png")
    try:
        if ico.exists():
            # CTkToplevel sometimes needs a deferred call on Windows
            def _set_ico() -> None:
                try:
                    window.iconbitmap(default=str(ico))
                except Exception:  # noqa: BLE001
                    try:
                        window.iconbitmap(str(ico))
                    except Exception:  # noqa: BLE001
                        pass

            window.after(1, _set_ico)
            try:
                window.iconbitmap(default=str(ico))
            except Exception:  # noqa: BLE001
                pass

        if png.exists():
            from PIL import Image, ImageTk

            img = Image.open(png).convert("RGBA")
            # Crisp downscale from master art
            photo = ImageTk.PhotoImage(img.resize((64, 64), Image.Resampling.LANCZOS))
            window.iconphoto(True, photo)
            _photo_refs.append(photo)
            # Keep on the widget so GC doesn't drop it
            window._ctrlnote_icon_photo = photo  # noqa: SLF001
    except Exception:  # noqa: BLE001
        pass

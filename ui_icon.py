"""
Иконка окна CtrlNote (заголовок и панель задач Windows).

Одинаково применяется к главному окну и к всплывающим диалогам.
"""

from __future__ import annotations

from typing import Any

from paths import asset_path

# Храним ссылки на картинки, чтобы их не удалил сборщик мусора Python
_photo_refs: list[Any] = []


def apply_window_icon(window: Any) -> None:
    """Ставит .ico и PNG-иконку на окно Tk / CustomTkinter."""
    ico = asset_path("icon.ico")
    png = asset_path("icon.png")
    try:
        if ico.exists():
            # На Windows для CTkToplevel иногда нужна отложенная установка
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
            # Уменьшаем мастер-картинку до чётких 64×64 для панели задач
            photo = ImageTk.PhotoImage(img.resize((64, 64), Image.Resampling.LANCZOS))
            window.iconphoto(True, photo)
            _photo_refs.append(photo)
            # Дублируем на самом виджете — иначе иконка может «пропасть»
            window._ctrlnote_icon_photo = photo  # noqa: SLF001
    except Exception:  # noqa: BLE001
        pass

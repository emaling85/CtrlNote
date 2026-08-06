"""
Главный файл CtrlNote.

Запускает приложение в трее Windows: иконка рядом с часами,
глобальная горячая клавиша и окно быстрой заметки для Obsidian.
"""

from __future__ import annotations

import sys
import threading
from pathlib import Path

from paths import asset_path
from single_instance import ensure_single_instance


def _load_icon():
    """Подбирает картинку для иконки в трее (маленькая, ~16–32 пикселя)."""
    from PIL import Image

    # Сначала пробуем специальную версию для трея
    tray = asset_path("icon-tray.png")
    if tray.exists():
        return Image.open(tray).convert("RGBA")

    # Если её нет — уменьшаем обычную иконку
    png = asset_path("icon.png")
    if png.exists():
        return Image.open(png).convert("RGBA").resize((32, 32), Image.Resampling.LANCZOS)

    # В крайнем случае рисуем иконку программно
    from make_icon import make_icon

    return make_icon(32)


class CtrlNoteApp:
    """«Мозг» приложения: связывает окно заметок, трей и горячую клавишу."""

    def __init__(self) -> None:
        # Тяжёлый UI подключаем только после проверки «один экземпляр»
        from capture_window import CaptureWindow

        self.window = CaptureWindow(
            on_saved=self._on_saved,
            on_hotkey_changed=self._register_hotkey,
        )
        self.icon = None  # иконка в системном трее
        self._hotkey = None  # слушатель горячей клавиши
        self._last_saved = ""  # путь к последней сохранённой заметке

    def _set_window_icon(self) -> None:
        """Ставит иконку CtrlNote в заголовок окна."""
        from ui_icon import apply_window_icon

        apply_window_icon(self.window.root)

    def _on_saved(self, path: str) -> None:
        """После сохранения заметки обновляет подсказку у иконки в трее."""
        self._last_saved = path
        if self.icon:
            self.icon.title = f"CtrlNote — сохранено: {Path(path).name}"

    def _schedule(self, callback) -> None:
        """Ставит действие в очередь главного потока интерфейса (безопасно для UI)."""
        self.window.root.after(0, callback)

    def _register_hotkey(self) -> None:
        """Читает горячую клавишу из настроек и регистрирует её в системе."""
        from config import load_config
        from hotkey_win import GlobalHotkey

        config = load_config()
        hotkey = (config.get("hotkey") or "ctrl+alt+n").strip().lower()
        if self._hotkey is not None:
            self._hotkey.stop()
            self._hotkey = None

        try:
            # По нажатию — показать/скрыть окно заметки
            self._hotkey = GlobalHotkey(hotkey, lambda: self._schedule(self.window.toggle))
            self._hotkey.start()
            print(f"Hotkey registered: {hotkey}")
        except Exception as exc:  # noqa: BLE001
            print(f"Failed to register hotkey '{hotkey}': {exc}", file=sys.stderr)
            # Если выбранная комбинация занята — пробуем стандартную
            if hotkey != "ctrl+alt+n":
                try:
                    self._hotkey = GlobalHotkey(
                        "ctrl+alt+n",
                        lambda: self._schedule(self.window.toggle),
                    )
                    self._hotkey.start()
                    print("Fallback hotkey registered: ctrl+alt+n")
                except Exception as fallback_exc:  # noqa: BLE001
                    print(f"Fallback hotkey failed: {fallback_exc}", file=sys.stderr)
                    self._hotkey = None

    def _build_tray(self):
        """Собирает меню правого клика по иконке в трее."""
        import pystray

        menu = pystray.Menu(
            pystray.MenuItem("Новая заметка", lambda: self._schedule(self.window.show), default=True),
            pystray.MenuItem("Настройки", lambda: self._schedule(self.window.open_settings)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Выход", self._quit),
        )
        return pystray.Icon("CtrlNote", _load_icon(), "CtrlNote", menu)

    def _quit(self, icon=None, item=None) -> None:  # noqa: ANN001, ARG002
        """Полностью закрывает приложение: хоткей, трей и окно."""
        if self._hotkey is not None:
            self._hotkey.stop()
            self._hotkey = None
        if self.icon:
            self.icon.stop()
        self._schedule(self.window.quit)

    def _finish_startup(self) -> None:
        """После старта цикла окна: иконка, хоткей, трей (чтобы первый кадр был лёгким)."""
        self._set_window_icon()
        self._register_hotkey()
        self.icon = self._build_tray()
        self.window.root.after(200, self._first_run_check)

        # Трей крутится в отдельном потоке, чтобы не блокировать окно
        tray_thread = threading.Thread(target=self.icon.run, daemon=True)
        tray_thread.start()

        print("CtrlNote is running.")
        print("Close via tray icon → Выход.")

    def run(self) -> None:
        """Быстро входит в цикл окна; трей и хоткей доделывает на первом idle-тике."""
        self.window.root.after(0, self._finish_startup)
        self.window.run()

    def _first_run_check(self) -> None:
        """При первом запуске показывает мастер настройки (выбор vault и т.д.)."""
        from onboarding import needs_onboarding, run_onboarding

        if not needs_onboarding():
            return

        dialog = run_onboarding(
            self.window.root,
            on_done=self._register_hotkey,
        )
        self.window.root.wait_window(dialog)
        self.window.hide()


def main() -> None:
    """Точка входа: не даём запустить вторую копию и стартуем приложение."""
    if not ensure_single_instance():
        print("CtrlNote already running.", file=sys.stderr)
        sys.exit(0)
    app = CtrlNoteApp()
    app.run()


if __name__ == "__main__":
    main()

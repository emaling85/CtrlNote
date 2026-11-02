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
        from i18n import init_from_config

        init_from_config()
        # Тяжёлый UI подключаем только после проверки «один экземпляр»
        from capture_window import CaptureWindow

        self.window = CaptureWindow(
            on_saved=self._on_saved,
            on_hotkey_changed=self._register_hotkey,
        )
        self.icon = None  # иконка в системном трее
        self._hotkey = None  # слушатель горячей клавиши
        self._trade_hotkey = None  # слушатель хоткея журнала сделок
        self._trade_window = None  # окно сделки создаём при первом вызове
        self._last_saved = ""  # путь к последней сохранённой заметке

    def _set_window_icon(self) -> None:
        """Ставит иконку CtrlNote в заголовок окна."""
        from ui_icon import apply_window_icon

        apply_window_icon(self.window.root)

    def _on_saved(self, path: str) -> None:
        """После сохранения заметки обновляет подсказку у иконки в трее."""
        from i18n import t

        self._last_saved = path
        if self.icon:
            self.icon.title = t("saved_tray", name=Path(path).name)

    def _on_trade_saved(self, path: str) -> None:
        """После записи сделки — подсказка у иконки в трее."""
        from i18n import t

        self._last_saved = path
        if self.icon:
            self.icon.title = t("trade_saved_tray", name=Path(path).stem)

    def _get_trade_window(self):
        """Окно журнала сделок (создаётся один раз, дальше только показывается)."""
        from i18n import get_language

        # Язык сменили в настройках — пересоздаём окно с новыми подписями
        if self._trade_window is not None and self._trade_window.lang != get_language():
            self._trade_window.win.destroy()
            self._trade_window = None
        if self._trade_window is None:
            from trade_window import TradeWindow

            self._trade_window = TradeWindow(self.window.root, on_saved=self._on_trade_saved)
            self._trade_window.on_hotkey_changed = self._register_trade_hotkey
        return self._trade_window

    def _toggle_trade(self) -> None:
        self._get_trade_window().toggle()

    def _show_trade(self) -> None:
        self._get_trade_window().show()

    def _register_trade_hotkey(self) -> None:
        """Регистрирует хоткей журнала трейдера (по умолчанию Ctrl+Alt+T)."""
        from config import load_config
        from edition import is_trader
        from hotkey_win import GlobalHotkey

        hotkey = (load_config().get("trade_hotkey") or "ctrl+alt+t").strip().lower()
        if self._trade_hotkey is not None:
            self._trade_hotkey.stop()
            self._trade_hotkey = None
        if not is_trader():
            return
        try:
            self._trade_hotkey = GlobalHotkey(hotkey, lambda: self._schedule(self._toggle_trade))
            self._trade_hotkey.start()
            print(f"Trade hotkey registered: {hotkey}")
        except Exception as exc:  # noqa: BLE001
            print(f"Failed to register trade hotkey '{hotkey}': {exc}", file=sys.stderr)
            self._trade_hotkey = None

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

    def _build_menu(self):
        """Меню правого клика по иконке в трее (на текущем языке)."""
        import pystray
        from edition import is_trader
        from i18n import t

        items = [pystray.MenuItem(t("new_note"), lambda: self._schedule(self.window.show), default=True)]
        if is_trader():
            items.append(pystray.MenuItem(t("trade_new"), lambda: self._schedule(self._show_trade)))
        items += [
            pystray.MenuItem(t("settings"), lambda: self._schedule(self.window.open_settings)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(t("exit"), self._quit),
        ]
        return pystray.Menu(*items)

    def _build_tray(self):
        """Собирает иконку в трее."""
        import pystray
        from edition import app_name

        return pystray.Icon("CtrlNote", _load_icon(), app_name(), self._build_menu())

    def _after_onboarding(self) -> None:
        """Мастер закрыт: язык мог смениться — обновляем подписи, трей и хоткеи."""
        from i18n import init_from_config

        init_from_config()
        self.window._apply_ui_language()  # noqa: SLF001
        if self.icon:
            self.icon.menu = self._build_menu()
            self.icon.update_menu()
        self._register_hotkey()
        self._register_trade_hotkey()

    def _quit(self, icon=None, item=None) -> None:  # noqa: ANN001, ARG002
        """Полностью закрывает приложение: хоткей, трей и окно."""
        for listener in (self._hotkey, self._trade_hotkey):
            if listener is not None:
                listener.stop()
        self._hotkey = None
        self._trade_hotkey = None
        if self.icon:
            self.icon.stop()
        self._schedule(self.window.quit)

    def _finish_startup(self) -> None:
        """После старта цикла окна: иконка, хоткей, трей (чтобы первый кадр был лёгким)."""
        self._set_window_icon()
        self._register_hotkey()
        self._register_trade_hotkey()
        self.icon = self._build_tray()
        self.window.root.after(200, self._first_run_check)

        # Трей крутится в отдельном потоке, чтобы не блокировать окно
        tray_thread = threading.Thread(target=self.icon.run, daemon=True)
        tray_thread.start()

        print("CtrlNote is running.")
        print("Close via tray icon → Exit.")

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
            on_done=self._after_onboarding,
        )
        self.window.root.wait_window(dialog)
        self.window.hide()


def _setup_log() -> None:
    """В собранном exe нет консоли: вывод и ошибки пишем в logs/ctrlnote.log рядом с программой."""
    if not getattr(sys, "frozen", False):
        return
    from config import APP_DIR

    try:
        log_dir = APP_DIR / "logs"
        log_dir.mkdir(exist_ok=True)
        log_path = log_dir / "ctrlnote.log"
        # Не даём логу разрастаться бесконечно
        if log_path.exists() and log_path.stat().st_size > 1_000_000:
            log_path.replace(log_dir / "ctrlnote.old.log")
        stream = log_path.open("a", encoding="utf-8", buffering=1)
    except OSError:
        return
    sys.stdout = sys.stderr = stream
    from datetime import datetime

    print(f"=== CtrlNote start {datetime.now():%Y-%m-%d %H:%M:%S} ===")


def main() -> None:
    """Точка входа: не даём запустить вторую копию и стартуем приложение."""
    from i18n import init_from_config

    _setup_log()

    if not ensure_single_instance():
        print("CtrlNote already running.", file=sys.stderr)
        sys.exit(0)
    init_from_config()
    app = CtrlNoteApp()
    app.run()


if __name__ == "__main__":
    main()

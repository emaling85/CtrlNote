"""CtrlNote — tray app with global hotkey for quick Obsidian notes."""

from __future__ import annotations

import sys
import threading
from pathlib import Path

import pystray
from PIL import Image

from capture_window import CaptureWindow
from config import load_config
from hotkey_win import GlobalHotkey
from paths import asset_path
from single_instance import ensure_single_instance


def _load_icon() -> Image.Image:
    """Windows tray is ~16–32px — use the dedicated tray render."""
    tray = asset_path("icon-tray.png")
    if tray.exists():
        return Image.open(tray).convert("RGBA")

    png = asset_path("icon.png")
    if png.exists():
        return Image.open(png).convert("RGBA").resize((32, 32), Image.Resampling.LANCZOS)

    from make_icon import make_icon

    return make_icon(32)


class CtrlNoteApp:
    def __init__(self) -> None:
        self.window = CaptureWindow(
            on_saved=self._on_saved,
            on_hotkey_changed=self._register_hotkey,
        )
        self.icon: pystray.Icon | None = None
        self._hotkey: GlobalHotkey | None = None
        self._last_saved = ""
        self._set_window_icon()

    def _set_window_icon(self) -> None:
        from ui_icon import apply_window_icon

        apply_window_icon(self.window.root)

    def _on_saved(self, path: str) -> None:
        self._last_saved = path
        if self.icon:
            self.icon.title = f"CtrlNote — сохранено: {Path(path).name}"

    def _schedule(self, callback) -> None:
        """Run UI callbacks on the Tk main thread."""
        self.window.root.after(0, callback)

    def _register_hotkey(self) -> None:
        config = load_config()
        hotkey = (config.get("hotkey") or "ctrl+alt+n").strip().lower()
        if self._hotkey is not None:
            self._hotkey.stop()
            self._hotkey = None

        try:
            self._hotkey = GlobalHotkey(hotkey, lambda: self._schedule(self.window.toggle))
            self._hotkey.start()
            print(f"Hotkey registered: {hotkey}")
        except Exception as exc:  # noqa: BLE001
            print(f"Failed to register hotkey '{hotkey}': {exc}", file=sys.stderr)
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

    def _build_tray(self) -> pystray.Icon:
        menu = pystray.Menu(
            pystray.MenuItem("Новая заметка", lambda: self._schedule(self.window.show), default=True),
            pystray.MenuItem("Настройки", lambda: self._schedule(self.window.open_settings)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Выход", self._quit),
        )
        return pystray.Icon("CtrlNote", _load_icon(), "CtrlNote", menu)

    def _quit(self, icon=None, item=None) -> None:  # noqa: ANN001, ARG002
        if self._hotkey is not None:
            self._hotkey.stop()
            self._hotkey = None
        if self.icon:
            self.icon.stop()
        self._schedule(self.window.quit)

    def run(self) -> None:
        self._register_hotkey()
        self.icon = self._build_tray()

        self.window.root.after(200, self._first_run_check)

        tray_thread = threading.Thread(target=self.icon.run, daemon=True)
        tray_thread.start()

        print("CtrlNote is running.")
        print("Close via tray icon → Выход.")
        self.window.run()

    def _first_run_check(self) -> None:
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
    if not ensure_single_instance():
        print("CtrlNote already running.", file=sys.stderr)
        sys.exit(0)
    app = CtrlNoteApp()
    app.run()


if __name__ == "__main__":
    main()

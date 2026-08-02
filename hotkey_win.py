"""Global hotkey via Win32 RegisterHotKey (no low-level keyboard hook)."""

from __future__ import annotations

import ctypes
import threading
from ctypes import wintypes
from typing import Callable

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000

WM_HOTKEY = 0x0312
WM_QUIT = 0x0012

HOTKEY_ID = 1

_VK_MAP = {
    "space": 0x20,
    "enter": 0x0D,
    "return": 0x0D,
    "tab": 0x09,
    "esc": 0x1B,
    "escape": 0x1B,
    "up": 0x26,
    "down": 0x28,
    "left": 0x25,
    "right": 0x27,
    "f1": 0x70,
    "f2": 0x71,
    "f3": 0x72,
    "f4": 0x73,
    "f5": 0x74,
    "f6": 0x75,
    "f7": 0x76,
    "f8": 0x77,
    "f9": 0x78,
    "f10": 0x79,
    "f11": 0x7A,
    "f12": 0x7B,
}


class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt", wintypes.POINT),
    ]


def parse_hotkey(hotkey: str) -> tuple[int, int]:
    """Parse 'ctrl+alt+n' into (modifiers, virtual_key)."""
    parts = [p.strip().lower() for p in hotkey.replace("-", "+").split("+") if p.strip()]
    mods = 0
    key: str | None = None
    for part in parts:
        if part in {"ctrl", "control", "ctl"}:
            mods |= MOD_CONTROL
        elif part == "alt":
            mods |= MOD_ALT
        elif part == "shift":
            mods |= MOD_SHIFT
        elif part in {"win", "windows", "super", "meta"}:
            mods |= MOD_WIN
        else:
            key = part

    if not key:
        raise ValueError(f"No key in hotkey: {hotkey!r}")

    if key in _VK_MAP:
        vk = _VK_MAP[key]
    elif len(key) == 1:
        vk = ord(key.upper())
    else:
        raise ValueError(f"Unsupported key in hotkey: {key!r}")

    return mods | MOD_NOREPEAT, vk


class GlobalHotkey:
    """Register a system-wide hotkey without hooking every keypress."""

    def __init__(self, hotkey: str, callback: Callable[[], None]) -> None:
        self.hotkey = hotkey
        self.callback = callback
        self._thread: threading.Thread | None = None
        self._thread_id = 0
        self._ready = threading.Event()
        self._error: str | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="CtrlNoteHotkey", daemon=True)
        self._thread.start()
        self._ready.wait(timeout=3)
        if self._error:
            raise RuntimeError(self._error)

    def stop(self) -> None:
        if self._thread_id:
            user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)
        self._thread = None
        self._thread_id = 0

    def _run(self) -> None:
        self._thread_id = kernel32.GetCurrentThreadId()
        try:
            mods, vk = parse_hotkey(self.hotkey)
        except ValueError as exc:
            self._error = str(exc)
            self._ready.set()
            return

        if not user32.RegisterHotKey(None, HOTKEY_ID, mods, vk):
            err = ctypes.get_last_error()
            self._error = f"RegisterHotKey failed for '{self.hotkey}' (error {err}). Maybe the shortcut is already taken?"
            self._ready.set()
            return

        self._ready.set()
        msg = MSG()
        while True:
            result = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if result == 0 or result == -1:
                break
            if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID:
                try:
                    self.callback()
                except Exception:  # noqa: BLE001
                    pass
            else:
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))

        user32.UnregisterHotKey(None, HOTKEY_ID)

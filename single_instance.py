"""Ensure only one CtrlNote process runs on Windows."""

from __future__ import annotations

import ctypes
import sys

ERROR_ALREADY_EXISTS = 183
_MUTEX_NAME = "Local\\CtrlNoteSingleInstanceMutex"
_mutex_handle = None


def ensure_single_instance() -> bool:
    """Return True if this process should continue, False if another is already running."""
    global _mutex_handle
    if sys.platform != "win32":
        return True

    kernel32 = ctypes.windll.kernel32
    _mutex_handle = kernel32.CreateMutexW(None, False, _MUTEX_NAME)
    if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
        return False
    return True

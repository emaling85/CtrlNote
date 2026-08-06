"""Configuration load/save for CtrlNote."""

from __future__ import annotations

import base64
import json
import sys
from pathlib import Path
from typing import Any


def get_app_dir() -> Path:
    """Directory for config.json — next to the .exe when frozen."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


APP_DIR = get_app_dir()
CONFIG_PATH = APP_DIR / "config.json"

_DPAPI_PREFIX = "dpapi:"


def _dpapi_protect(plain: str) -> str:
    """Encrypt string with Windows DPAPI (current user). Falls back to plaintext."""
    if not plain or sys.platform != "win32":
        return plain
    try:
        import ctypes
        import ctypes.wintypes

        class DATA_BLOB(ctypes.Structure):
            _fields_ = [("cbData", ctypes.wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32
        raw = plain.encode("utf-8")
        blob_in = DATA_BLOB(len(raw), ctypes.create_string_buffer(raw, len(raw)))
        blob_out = DATA_BLOB()
        if not crypt32.CryptProtectData(
            ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)
        ):
            return plain
        try:
            encrypted = ctypes.string_at(blob_out.pbData, blob_out.cbData)
        finally:
            kernel32.LocalFree(blob_out.pbData)
        return _DPAPI_PREFIX + base64.b64encode(encrypted).decode("ascii")
    except Exception:
        return plain


def _dpapi_unprotect(value: str) -> str:
    if not value.startswith(_DPAPI_PREFIX) or sys.platform != "win32":
        return value
    try:
        import ctypes
        import ctypes.wintypes

        class DATA_BLOB(ctypes.Structure):
            _fields_ = [("cbData", ctypes.wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32
        raw = base64.b64decode(value[len(_DPAPI_PREFIX) :].encode("ascii"))
        blob_in = DATA_BLOB(len(raw), ctypes.create_string_buffer(raw, len(raw)))
        blob_out = DATA_BLOB()
        if not crypt32.CryptUnprotectData(
            ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)
        ):
            return ""
        try:
            return ctypes.string_at(blob_out.pbData, blob_out.cbData).decode("utf-8")
        finally:
            kernel32.LocalFree(blob_out.pbData)
    except Exception:
        return ""


DEFAULT_CONFIG: dict[str, Any] = {
    "vault_path": "",
    "hotkey": "ctrl+alt+n",
    "last_folder": "",  # relative to vault, "" means vault root
    "autostart": False,
    "auto_folder": True,  # pick vault folder from active window
    "voice_language": "ru",
    "whisper_model": "small",  # tiny | base | small | medium
    "voice_engine": "local",  # local | openai
    "openai_api_key": "",
    "save_voice_audio": False,
    "link_daily_note": False,
    "append_daily_note": False,
    "daily_note_folder": "",
    "daily_note_format": "YYYY-MM-DD",
}


def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return dict(DEFAULT_CONFIG)
    try:
        with CONFIG_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return dict(DEFAULT_CONFIG)

    config = dict(DEFAULT_CONFIG)
    config.update({k: v for k, v in data.items() if k in DEFAULT_CONFIG})
    key = str(config.get("openai_api_key", "") or "")
    config["openai_api_key"] = _dpapi_unprotect(key)
    return config


def save_config(config: dict[str, Any]) -> None:
    data = dict(DEFAULT_CONFIG)
    data.update({k: v for k, v in config.items() if k in DEFAULT_CONFIG})
    plain_key = str(data.get("openai_api_key", "") or "")
    data["openai_api_key"] = _dpapi_protect(plain_key) if plain_key else ""
    with CONFIG_PATH.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def is_configured(config: dict[str, Any] | None = None) -> bool:
    cfg = config if config is not None else load_config()
    vault = Path(cfg.get("vault_path", "")).expanduser()
    return bool(cfg.get("vault_path")) and vault.is_dir()

"""Configuration load/save for CtrlNote."""

from __future__ import annotations

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
    "save_voice_audio": True,
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
    return config


def save_config(config: dict[str, Any]) -> None:
    data = dict(DEFAULT_CONFIG)
    data.update({k: v for k, v in config.items() if k in DEFAULT_CONFIG})
    with CONFIG_PATH.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def is_configured(config: dict[str, Any] | None = None) -> bool:
    cfg = config if config is not None else load_config()
    vault = Path(cfg.get("vault_path", "")).expanduser()
    return bool(cfg.get("vault_path")) and vault.is_dir()

"""
Настройки CtrlNote: чтение и запись файла config.json.

Хранит путь к vault Obsidian, горячую клавишу, голос и другие параметры.
Ключ OpenAI на Windows шифруется средствами системы (DPAPI), чтобы не лежал открытым текстом.
"""

from __future__ import annotations

import base64
import json
import sys
from pathlib import Path
from typing import Any


def get_app_dir() -> Path:
    """Папка, где лежит config.json — рядом с .exe или с исходниками."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


APP_DIR = get_app_dir()
CONFIG_PATH = APP_DIR / "config.json"

# Метка: значение после неё — зашифрованный ключ, а не обычный текст
_DPAPI_PREFIX = "dpapi:"


class SecretStorageError(RuntimeError):
    """Не удалось зашифровать секрет — plaintext на диск не пишем."""


def _dpapi_protect(plain: str) -> str:
    """Шифрует строку через Windows DPAPI. При сбое — ошибка (не plaintext)."""
    if not plain:
        return ""
    if sys.platform != "win32":
        raise SecretStorageError("DPAPI доступен только на Windows")
    try:
        import ctypes
        import ctypes.wintypes

        class DATA_BLOB(ctypes.Structure):
            _fields_ = [("cbData", ctypes.wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32
        raw = plain.encode("utf-8")
        # Буфер должен жить, пока Windows API шифрует данные
        buf = ctypes.create_string_buffer(raw, len(raw))
        blob_in = DATA_BLOB(len(raw), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
        blob_out = DATA_BLOB()
        if not crypt32.CryptProtectData(
            ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)
        ):
            raise SecretStorageError("CryptProtectData failed")
        try:
            encrypted = ctypes.string_at(blob_out.pbData, blob_out.cbData)
        finally:
            kernel32.LocalFree(blob_out.pbData)
        return _DPAPI_PREFIX + base64.b64encode(encrypted).decode("ascii")
    except SecretStorageError:
        raise
    except Exception as exc:
        raise SecretStorageError(f"DPAPI protect failed: {exc}") from exc


def _dpapi_unprotect(value: str) -> str:
    """Расшифровывает значение, сохранённое через _dpapi_protect. Иначе возвращает как есть."""
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
        buf = ctypes.create_string_buffer(raw, len(raw))
        blob_in = DATA_BLOB(len(raw), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
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


# Значения по умолчанию, если config.json ещё нет или поле отсутствует
DEFAULT_CONFIG: dict[str, Any] = {
    "vault_path": "",  # папка vault Obsidian
    "hotkey": "ctrl+alt+n",  # глобальная горячая клавиша
    "last_folder": "",  # последняя выбранная подпапка ("" = корень)
    "autostart": False,  # запускать ли вместе с Windows
    "auto_folder": True,  # подставлять папку по заголовку активного окна
    "voice_language": "ru",  # язык распознавания речи
    "whisper_model": "small",  # tiny | base | small | medium
    "voice_engine": "local",  # local = на компьютере, openai = через интернет
    "openai_api_key": "",  # ключ API (в файле хранится зашифрованным)
    "save_voice_audio": False,  # сохранять ли записи микрофона на диск
    "link_daily_note": False,  # добавлять [[сегодня]] в конец заметки
    "append_daily_note": False,  # писать ссылку в файл ежедневной заметки
    "daily_note_folder": "",  # папка для daily notes
    "daily_note_format": "YYYY-MM-DD",  # формат имени файла дня
}


def load_config() -> dict[str, Any]:
    """Загружает настройки с диска. При ошибке или отсутствии файла — значения по умолчанию."""
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
    """Сохраняет настройки в config.json (ключ API перед записью шифруется)."""
    data = dict(DEFAULT_CONFIG)
    data.update({k: v for k, v in config.items() if k in DEFAULT_CONFIG})
    plain_key = str(data.get("openai_api_key", "") or "")
    data["openai_api_key"] = _dpapi_protect(plain_key) if plain_key else ""
    with CONFIG_PATH.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def is_configured(config: dict[str, Any] | None = None) -> bool:
    """Проверяет, указан ли существующий путь к vault — иначе нужна первичная настройка."""
    cfg = config if config is not None else load_config()
    vault = Path(cfg.get("vault_path", "")).expanduser()
    return bool(cfg.get("vault_path")) and vault.is_dir()

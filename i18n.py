"""UI language strings (English + Russian). Voice language stays separate."""

from __future__ import annotations

from typing import Any

# ui_language in config: "en" | "ru"
STRINGS: dict[str, dict[str, str]] = {
    "en": {
        "vault_root": "(vault root)",
        "vault_root_folder": "./(vault root)",
        "no_template": "(no template)",
        "paste": "Paste",
        "templates": "Templates",
        "voice_again": "Voice again",
        "cancel": "Cancel",
        "save": "Save",
        "settings": "Settings",
        "new_note": "New note",
        "exit": "Exit",
        "saved_tray": "CtrlNote — saved: {name}",
        "drawing_added": "Drawing added",
        "recording": "Recording…",
        "transcribing": "Transcribing…",
        "downloading_model": "Downloading model…",
        "loading_model": "Loading model…",
        "nothing_recognized": "Nothing recognized — speak longer, or check Voice language in Settings",
        "voice_deps": "Voice dependencies are not installed.",
        "mic_error": "Could not open microphone:\n{exc}",
        "rec_error": "Recording error:\n{exc}",
        "transcribe_error": "Could not transcribe:\n{exc}",
        "save_error": "Could not save:\n{exc}",
        "empty_note": "Write something or paste an image",
        "clipboard_empty": "Clipboard is empty",
        "select_vault": "Select vault",
        "obsidian_vault": "Obsidian vault",
        "browse": "Browse",
        "hotkey": "Hotkey",
        "start_windows": "Start with Windows",
        "auto_folder": "Auto-select folder from active window",
        "voice": "Voice",
        "whisper_model": "Whisper model (local)",
        "openai_key": "OpenAI API key (for openai)",
        "ui_language": "App language",
        "voice_language": "Voice language",
        "save_audio": "Save audio to recordings",
        "daily_note": "Daily note",
        "link_daily": "Append [[today]] at the end of the note",
        "append_daily": "Write a link into Obsidian daily note file",
        "daily_folder": "Daily note folder (empty = vault root)",
        "daily_format": "Daily note name format",
        "settings_title": "CtrlNote Settings",
        "templates_title": "Templates",
        "list": "List",
        "name": "Name",
        "template_body": "Template body",
        "new": "New",
        "delete": "Delete",
        "close": "Close",
        "enter_template_name": "Enter a template name",
        "delete_template": "Delete this template?",
        "replace_template": "Replace current note text with this template?",
        "secret_error": "Could not securely save API key:\n{exc}",
        "settings_save_error": "Could not save settings:\n{exc}",
        "autostart_error": "Could not change autostart:\n{exc}",
        "hotkey_error": "Could not apply hotkey:\n{exc}",
        "onboard_title": "Set up CtrlNote",
        "onboard_back": "Back",
        "onboard_next": "Next",
        "onboard_done": "Done",
        "onboard_vault_title": "Where should notes go?",
        "onboard_vault_sub": "Choose your Obsidian vault folder — the folder with your .md files.",
        "onboard_hotkey_title": "Hotkey & startup",
        "onboard_hotkey_sub": "Pick a global shortcut. Optional: start with Windows.",
        "onboard_voice_title": "Voice (optional)",
        "onboard_voice_sub": "Local Whisper on this PC, or OpenAI in the cloud.",
        "onboard_later": "You can change everything later in Settings.",
        "pick_vault_warn": "Please select an existing vault folder.",
        "paint_title": "Draw",
        "paint_size": "Size",
        "paint_clear": "Clear",
        "paint_paste": "Paste",
        "paint_shot": "Shot",
        "paint_cancel": "Cancel",
        "paint_insert": "Insert into note",
        "paint_hint": "Empty canvas · Shot / Paste (Ctrl+V) for background",
        "paint_tools": "Pen,Eraser,Line,Rect,Oval,Fill",
    },
    "ru": {
        "vault_root": "(корень vault)",
        "vault_root_folder": "./(корень vault)",
        "no_template": "(без шаблона)",
        "paste": "Вставить",
        "templates": "Шаблоны",
        "voice_again": "↻ Голос",
        "cancel": "Отмена",
        "save": "Сохранить",
        "settings": "Настройки",
        "new_note": "Новая заметка",
        "exit": "Выход",
        "saved_tray": "CtrlNote — сохранено: {name}",
        "drawing_added": "Рисунок добавлен",
        "recording": "Запись…",
        "transcribing": "Расшифровка…",
        "downloading_model": "Скачивание модели…",
        "loading_model": "Загрузка модели…",
        "nothing_recognized": "Ничего не распознано — говорите дольше или проверьте язык голоса в настройках",
        "voice_deps": "Не установлены зависимости для голоса.",
        "mic_error": "Не удалось открыть микрофон:\n{exc}",
        "rec_error": "Ошибка записи:\n{exc}",
        "transcribe_error": "Не удалось распознать:\n{exc}",
        "save_error": "Не удалось сохранить:\n{exc}",
        "empty_note": "Напишите текст или вставьте картинку",
        "clipboard_empty": "Буфер обмена пуст",
        "select_vault": "Выберите vault",
        "obsidian_vault": "Obsidian vault",
        "browse": "Обзор",
        "hotkey": "Горячая клавиша",
        "start_windows": "Запускать с Windows",
        "auto_folder": "Папка по активному окну",
        "voice": "Голос",
        "whisper_model": "Модель Whisper (local)",
        "openai_key": "OpenAI API key (для openai)",
        "ui_language": "Язык приложения",
        "voice_language": "Язык голоса",
        "save_audio": "Сохранять аудио в recordings",
        "daily_note": "Daily note",
        "link_daily": "Добавлять [[сегодня]] в конец заметки",
        "append_daily": "Писать ссылку в файл daily note",
        "daily_folder": "Папка daily note (пусто = корень)",
        "daily_format": "Формат имени дня",
        "settings_title": "Настройки CtrlNote",
        "templates_title": "Шаблоны",
        "list": "Список",
        "name": "Имя",
        "template_body": "Текст шаблона",
        "new": "Новый",
        "delete": "Удалить",
        "close": "Закрыть",
        "enter_template_name": "Введите имя шаблона",
        "delete_template": "Удалить этот шаблон?",
        "replace_template": "Заменить текст заметки этим шаблоном?",
        "secret_error": "Не удалось безопасно сохранить API-ключ:\n{exc}",
        "settings_save_error": "Не удалось сохранить настройки:\n{exc}",
        "autostart_error": "Не удалось изменить автозапуск:\n{exc}",
        "hotkey_error": "Не удалось применить горячую клавишу:\n{exc}",
        "onboard_title": "Настройка CtrlNote",
        "onboard_back": "Назад",
        "onboard_next": "Далее",
        "onboard_done": "Готово",
        "onboard_vault_title": "Куда сохранять заметки?",
        "onboard_vault_sub": "Выберите папку vault Obsidian — обычная папка с вашими .md файлами.",
        "onboard_hotkey_title": "Горячая клавиша и автозапуск",
        "onboard_hotkey_sub": "Выберите глобальную комбинацию. По желанию — автозапуск с Windows.",
        "onboard_voice_title": "Голос (по желанию)",
        "onboard_voice_sub": "Локальный Whisper на этом ПК или OpenAI в облаке.",
        "onboard_later": "Позже всё можно изменить в ⚙ Настройки.",
        "pick_vault_warn": "Укажите существующую папку vault.",
        "paint_title": "Рисунок",
        "paint_size": "Толщина",
        "paint_clear": "Очистить",
        "paint_paste": "Вставить",
        "paint_shot": "Скрин",
        "paint_cancel": "Отмена",
        "paint_insert": "Вставить в заметку",
        "paint_hint": "Пустой холст · Скрин / Вставить (Ctrl+V) — фон",
        "paint_tools": "Перо,Ластик,Линия,Прямоуг,Круг,Заливка",
    },
}

_current: str = "en"


def normalize_lang(code: str | None) -> str:
    raw = (code or "en").strip().lower()
    if raw.startswith("ru"):
        return "ru"
    return "en"


def set_language(code: str) -> None:
    global _current
    _current = normalize_lang(code)


def get_language() -> str:
    return _current


def init_from_config(config: dict[str, Any] | None = None) -> str:
    """Load ui_language from config (or default) into runtime."""
    if config is None:
        from config import load_config

        config = load_config()
    lang = normalize_lang(str(config.get("ui_language", "en") or "en"))
    set_language(lang)
    return lang


def t(key: str, **kwargs: Any) -> str:
    """Translate key for current UI language."""
    table = STRINGS.get(_current) or STRINGS["en"]
    text = table.get(key) or STRINGS["en"].get(key) or key
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, ValueError):
            return text
    return text


def none_template_label() -> str:
    return t("no_template")


def paint_tools() -> list[str]:
    return [part.strip() for part in t("paint_tools").split(",") if part.strip()]

"""
Шаблоны заметок: готовые заготовки + файл templates.json, который можно править.

Пользователь выбирает шаблон в окне быстрого ввода — подставляется готовый текст.
"""

from __future__ import annotations

import json
import uuid
from copy import deepcopy
from typing import Any

from config import APP_DIR

TEMPLATES_PATH = APP_DIR / "templates.json"

# Встроенные шаблоны при первом запуске (если файла ещё нет)
DEFAULT_TEMPLATES: list[dict[str, str]] = [
    {
        "id": "idea",
        "name": "Идея",
        "body": "# Идея\n\n\n\n#идея\n",
    },
    {
        "id": "bug",
        "name": "Баг",
        "body": (
            "# Баг\n\n"
            "**Где:** \n"
            "**Что случилось:** \n"
            "**Ожидал:** \n\n"
            "#баг\n"
        ),
    },
    {
        "id": "task",
        "name": "Задача",
        "body": "# Задача\n\n- [ ] \n\n#задача\n",
    },
    {
        "id": "meeting",
        "name": "Встреча",
        "body": (
            "# Встреча\n\n"
            "**С кем:** \n"
            "**О чём:** \n"
            "**Договорённости:** \n\n"
            "#встреча\n"
        ),
    },
]

# Пункт в списке: «не использовать шаблон»
NONE_LABEL = "(без шаблона)"


def _normalize(item: dict[str, Any]) -> dict[str, str] | None:
    """Приводит запись шаблона к единому виду; без имени — отбрасывает."""
    name = str(item.get("name", "")).strip()
    body = str(item.get("body", ""))
    if not name:
        return None
    tid = str(item.get("id", "")).strip() or uuid.uuid4().hex[:10]
    return {"id": tid, "name": name, "body": body}


def load_templates() -> list[dict[str, str]]:
    """Читает шаблоны с диска. При проблемах — записывает и возвращает встроенные."""
    if not TEMPLATES_PATH.exists():
        templates = deepcopy(DEFAULT_TEMPLATES)
        save_templates(templates)
        return templates
    try:
        with TEMPLATES_PATH.open("r", encoding="utf-8") as f:
            raw = json.load(f)
    except (json.JSONDecodeError, OSError):
        templates = deepcopy(DEFAULT_TEMPLATES)
        save_templates(templates)
        return templates

    if not isinstance(raw, list):
        templates = deepcopy(DEFAULT_TEMPLATES)
        save_templates(templates)
        return templates

    templates: list[dict[str, str]] = []
    for item in raw:
        if isinstance(item, dict):
            norm = _normalize(item)
            if norm:
                templates.append(norm)
    if not templates:
        templates = deepcopy(DEFAULT_TEMPLATES)
        save_templates(templates)
    return templates


def save_templates(templates: list[dict[str, str]]) -> None:
    """Записывает список шаблонов в templates.json."""
    clean: list[dict[str, str]] = []
    for item in templates:
        norm = _normalize(item)
        if norm:
            clean.append(norm)
    with TEMPLATES_PATH.open("w", encoding="utf-8") as f:
        json.dump(clean, f, ensure_ascii=False, indent=2)


def add_template(name: str, body: str) -> dict[str, str]:
    """Создаёт новый шаблон и сохраняет его."""
    templates = load_templates()
    item = {"id": uuid.uuid4().hex[:10], "name": name.strip(), "body": body}
    templates.append(item)
    save_templates(templates)
    return item


def update_template(template_id: str, name: str, body: str) -> bool:
    """Обновляет существующий шаблон по id. True — нашли и сохранили."""
    templates = load_templates()
    for item in templates:
        if item["id"] == template_id:
            item["name"] = name.strip()
            item["body"] = body
            save_templates(templates)
            return True
    return False


def delete_template(template_id: str) -> bool:
    """Удаляет шаблон по id. True — удалили."""
    templates = load_templates()
    new_list = [t for t in templates if t["id"] != template_id]
    if len(new_list) == len(templates):
        return False
    save_templates(new_list)
    return True


def get_template_by_name(name: str) -> dict[str, str] | None:
    """Находит шаблон по отображаемому названию."""
    for item in load_templates():
        if item["name"] == name:
            return item
    return None


def template_names() -> list[str]:
    """Список названий для выпадающего меню (с пунктом «без шаблона»)."""
    return [NONE_LABEL, *[t["name"] for t in load_templates()]]

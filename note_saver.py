"""
Сохранение markdown-заметок в папку vault Obsidian.

Придумывает имя файла, кладёт картинки рядом и не допускает коллизий имён.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from vault_paths import resolve_under_vault, safe_attachment_name


if TYPE_CHECKING:
    from PIL.Image import Image as PilImage


# Символы, которые Windows не разрешает в именах файлов
_INVALID_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
# Строка, похожая только на вставку картинки (не годится как заголовок)
_IMAGE_LINE = re.compile(r"^!\[\[.+\]\]\s*$|^!\[.*\]\(.+\)\s*$")
# Убираем # из заголовков markdown (# Заголовок → Заголовок)
_HEADING_PREFIX = re.compile(r"^#{1,6}\s*")


def sanitize_filename(name: str, max_length: int = 80) -> str:
    """Очищает строку до безопасного имени файла."""
    cleaned = _INVALID_CHARS.sub("", name).strip().rstrip(".")
    cleaned = re.sub(r"\s+", " ", cleaned)
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length].rstrip()
    return cleaned


def title_from_content_line(line: str) -> str:
    """Делает из первой строки заметки чистое название файла."""
    text = line.strip()
    text = _HEADING_PREFIX.sub("", text).strip()
    text = text.strip("#").strip()
    return sanitize_filename(text)


def build_note_filename(content: str, now: datetime | None = None) -> str:
    """
    Имя файла заметки: дата-время + заголовок из первой осмысленной строки.

    Если подходящей строки нет — только дата и время.
    """
    stamp = (now or datetime.now()).strftime("%Y-%m-%d %H-%M")
    first_line = ""
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        # Картинки в начале не считаем заголовком
        if _IMAGE_LINE.match(stripped):
            continue
        first_line = stripped
        break

    if first_line:
        title = title_from_content_line(first_line)
        if title:
            return f"{stamp} {title}.md"
    return f"{stamp}.md"


def unique_path(directory: Path, filename: str) -> Path:
    """
    Подбирает путь, который ещё не занят.

    Если файл уже есть — добавляет « (2)», « (3)» и т.д.
    """
    safe_name = Path(filename).name
    if not safe_name or safe_name in {".", ".."} or ".." in Path(filename).parts:
        safe_name = safe_attachment_name(filename)
    candidate = directory / safe_name
    if not candidate.exists():
        return candidate

    stem = candidate.stem
    suffix = candidate.suffix
    index = 2
    while True:
        candidate = directory / f"{stem} ({index}){suffix}"
        if not candidate.exists():
            return candidate
        index += 1


def list_vault_folders(vault_path: str | Path, max_depth: int = 2) -> list[str]:
    """
    Список подпапок vault (относительно корня).

    Пустая строка '' означает сам корень vault. Скрытые папки (с точкой) пропускаются.
    """
    vault = Path(vault_path).expanduser().resolve()
    if not vault.is_dir():
        return [""]

    folders: list[str] = [""]
    for path in sorted(vault.rglob("*")):
        if not path.is_dir():
            continue
        try:
            parts = path.resolve().relative_to(vault).parts
        except ValueError:
            continue
        # Не показываем .obsidian и подобные служебные папки
        if any(part.startswith(".") for part in parts):
            continue
        if len(parts) > max_depth:
            continue
        folders.append(str(path.relative_to(vault)).replace("\\", "/"))
    return folders


def save_note(
    content: str,
    vault_path: str | Path,
    relative_folder: str = "",
    attachments: list[tuple[str, "PilImage"]] | None = None,
) -> Path:
    """
    Сохраняет текст заметки и картинки в выбранную папку vault.

    Возвращает путь к созданному .md файлу.
    """
    vault = Path(vault_path).expanduser().resolve()
    if not vault.is_dir():
        raise FileNotFoundError(f"Vault folder not found: {vault}")

    # Папка назначения (корень или подпапка)
    target_dir = resolve_under_vault(vault, relative_folder) if relative_folder else vault
    target_dir.mkdir(parents=True, exist_ok=True)

    # Сначала сохраняем вложения и при необходимости правим ссылки в тексте
    for image_name, image in attachments or []:
        safe_name = safe_attachment_name(image_name)
        image_path = unique_path(target_dir, safe_name)
        if image_path.name != image_name:
            content = content.replace(f"![[{image_name}]]", f"![[{image_path.name}]]")
        image.save(image_path, format="PNG")

    filename = build_note_filename(content)
    path = unique_path(target_dir, filename)
    # Ещё раз убеждаемся, что файл внутри vault
    resolve_under_vault(vault, str(path.resolve().relative_to(vault)))
    path.write_text(content.rstrip() + "\n", encoding="utf-8")
    return path

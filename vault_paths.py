"""
Безопасные пути внутри vault Obsidian.

Все сохранения заметок и вложений должны оставаться внутри выбранной папки vault.
Это защита от случайной записи «куда угодно» на диске.
"""

from __future__ import annotations

from pathlib import Path


class VaultPathError(ValueError):
    """Ошибка: путь пытается выйти за пределы vault."""


def resolve_under_vault(vault_path: str | Path, *relative_parts: str) -> Path:
    """
    Собирает полный путь внутри vault из относительных кусков.

    Пустые части пропускаются. Запрещены абсолютные пути и «..» (выход наверх).
    Итоговый путь обязан лежать строго внутри vault.
    """
    vault = Path(vault_path).expanduser().resolve()
    segments: list[str] = []
    for raw in relative_parts:
        if raw is None:
            continue
        text = str(raw).strip().replace("\\", "/")
        if not text or text == ".":
            continue
        part = Path(text)
        # Абсолютный путь или сетевой UNC — нельзя
        if part.is_absolute() or (len(part.parts) > 0 and part.parts[0] in {part.anchor, "/"}):
            raise VaultPathError(f"Absolute path not allowed under vault: {raw!r}")
        # «Подняться на уровень выше» тоже нельзя
        if ".." in part.parts:
            raise VaultPathError(f"Parent traversal not allowed under vault: {raw!r}")
        segments.extend(p for p in part.parts if p not in {"", "."})

    target = vault.joinpath(*segments).resolve() if segments else vault
    # Финальная проверка: путь действительно внутри vault
    try:
        target.relative_to(vault)
    except ValueError as exc:
        raise VaultPathError(f"Path escapes vault: {target} not under {vault}") from exc
    return target


def safe_attachment_name(name: str) -> str:
    """Оставляет только имя файла вложения (без папок и «..» как целого компонента)."""
    base = Path(str(name).replace("\\", "/")).name
    if not base or base in {".", ".."}:
        raise VaultPathError(f"Invalid attachment name: {name!r}")
    return base

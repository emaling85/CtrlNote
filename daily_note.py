"""
Связь с ежедневной заметкой Obsidian (daily note).

Может добавить ссылку [[сегодня]] в конец быстрой заметки
или дописать пункт в файл дня.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from vault_paths import VaultPathError, resolve_under_vault


def daily_note_name(fmt: str = "YYYY-MM-DD", now: datetime | None = None) -> str:
    """Имя файла/ссылки на сегодняшний день по выбранному формату даты."""
    stamp = now or datetime.now()
    mapping = {
        "YYYY-MM-DD": stamp.strftime("%Y-%m-%d"),
        "DD-MM-YYYY": stamp.strftime("%d-%m-%Y"),
        "YYYYMMDD": stamp.strftime("%Y%m%d"),
    }
    return mapping.get(fmt, stamp.strftime("%Y-%m-%d"))


def daily_wikilink(fmt: str = "YYYY-MM-DD", now: datetime | None = None) -> str:
    """Wiki-ссылка Obsidian на заметку дня, например [[2026-08-06]]."""
    return f"[[{daily_note_name(fmt, now)}]]"


def append_daily_link(content: str, fmt: str = "YYYY-MM-DD", now: datetime | None = None) -> str:
    """Добавляет в конец текста ссылку на сегодня, если её ещё нет."""
    link = daily_wikilink(fmt, now)
    text = content.rstrip()
    if link in text:
        return text + "\n"
    if not text:
        return f"{link}\n"
    return f"{text}\n\n{link}\n"


def _safe_daily_path(vault: Path, target_dir: Path, name: str) -> Path | None:
    """Безопасный путь к файлу дня внутри vault; отсекает symlink/hardlink «наружу»."""
    path = target_dir / f"{name}.md"
    try:
        rel = path.resolve().relative_to(vault)
    except ValueError:
        return None
    # Ещё раз проверяем через общий хелпер (в т.ч. junctions)
    try:
        path = resolve_under_vault(vault, *rel.parts)
    except VaultPathError:
        return None

    if path.exists() or path.is_symlink():
        if path.is_symlink():
            try:
                path.resolve().relative_to(vault)
            except ValueError:
                return None
        try:
            if path.exists() and path.stat().st_nlink > 1:
                # Жёсткая ссылка на другое имя (возможно снаружи) — разрываем перед записью
                existing = path.read_text(encoding="utf-8")
                path.unlink()
                path.write_text(existing, encoding="utf-8")
        except OSError:
            return None
    return path


def append_to_daily_file(
    vault_path: str | Path,
    note_title: str,
    *,
    folder: str = "",
    fmt: str = "YYYY-MM-DD",
    now: datetime | None = None,
) -> Path | None:
    """
    Дописывает в файл ежедневной заметки пункт со ссылкой на сохранённую заметку.

    Если файла дня ещё нет — создаёт его. Если такая ссылка уже есть — ничего не меняет.
    """
    vault = Path(vault_path).expanduser().resolve()
    if not vault.is_dir():
        return None

    name = daily_note_name(fmt, now)
    try:
        target_dir = resolve_under_vault(vault, folder) if folder else vault
    except VaultPathError:
        return None
    target_dir.mkdir(parents=True, exist_ok=True)
    path = _safe_daily_path(vault, target_dir, name)
    if path is None:
        return None

    line = f"- [[{note_title}]]"
    if path.exists():
        existing = path.read_text(encoding="utf-8")
        if line in existing or note_title in existing:
            return path
        sep = "" if existing.endswith("\n") else "\n"
        path.write_text(existing + f"{sep}{line}\n", encoding="utf-8")
    else:
        path.write_text(f"# {name}\n\n{line}\n", encoding="utf-8")
    return path

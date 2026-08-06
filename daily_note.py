"""Optional link / append to Obsidian daily note."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from vault_paths import VaultPathError, resolve_under_vault


def daily_note_name(fmt: str = "YYYY-MM-DD", now: datetime | None = None) -> str:
    stamp = now or datetime.now()
    mapping = {
        "YYYY-MM-DD": stamp.strftime("%Y-%m-%d"),
        "DD-MM-YYYY": stamp.strftime("%d-%m-%Y"),
        "YYYYMMDD": stamp.strftime("%Y%m%d"),
    }
    return mapping.get(fmt, stamp.strftime("%Y-%m-%d"))


def daily_wikilink(fmt: str = "YYYY-MM-DD", now: datetime | None = None) -> str:
    return f"[[{daily_note_name(fmt, now)}]]"


def append_daily_link(content: str, fmt: str = "YYYY-MM-DD", now: datetime | None = None) -> str:
    link = daily_wikilink(fmt, now)
    text = content.rstrip()
    if link in text:
        return text + "\n"
    if not text:
        return f"{link}\n"
    return f"{text}\n\n{link}\n"


def append_to_daily_file(
    vault_path: str | Path,
    note_title: str,
    *,
    folder: str = "",
    fmt: str = "YYYY-MM-DD",
    now: datetime | None = None,
) -> Path | None:
    """Append a bullet about the capture into today's daily note (create if missing)."""
    vault = Path(vault_path).expanduser().resolve()
    if not vault.is_dir():
        return None

    name = daily_note_name(fmt, now)
    try:
        target_dir = resolve_under_vault(vault, folder) if folder else vault
    except VaultPathError:
        return None
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / f"{name}.md"

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

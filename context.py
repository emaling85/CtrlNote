"""Detect active window context and map/create an Obsidian vault folder."""

from __future__ import annotations

import re
import sys
from pathlib import Path

from note_saver import list_vault_folders, sanitize_filename
from vault_paths import VaultPathError, resolve_under_vault

_EDITOR_SUFFIXES = (
    " - Cursor",
    " — Cursor",
    " - Visual Studio Code",
    " — Visual Studio Code",
    " - VSCodium",
    " - Code - OSS",
    " - Windsurf",
    " - Trae",
    " - Antigravity",
    " - Sublime Text",
    " - Notepad++",
)

_BROWSER_SUFFIXES = (
    " - Google Chrome",
    " — Google Chrome",
    " - Microsoft Edge",
    " — Microsoft Edge",
    " - Microsoft​ Edge",  # narrow no-break space variants appear sometimes
    " - Mozilla Firefox",
    " — Mozilla Firefox",
    " - Opera",
    " - Brave",
    " - Vivaldi",
    " - Яндекс Браузер",
    " - Yandex",
)

# Site / app markers in titles → canonical folder name
_KNOWN_CONTEXTS: dict[str, str] = {
    "youtube": "YouTube",
    "youtu.be": "YouTube",
    "twitter": "Twitter",
    "x.com": "X",
    "reddit": "Reddit",
    "github": "GitHub",
    "gitlab": "GitLab",
    "notion": "Notion",
    "figma": "Figma",
    "discord": "Discord",
    "telegram": "Telegram",
    "spotify": "Spotify",
    "twitch": "Twitch",
    "instagram": "Instagram",
    "tiktok": "TikTok",
    "linkedin": "LinkedIn",
    "habr": "Habr",
    "medium": "Medium",
    "stackoverflow": "StackOverflow",
    "stack overflow": "StackOverflow",
    "gmail": "Gmail",
    "google docs": "Google Docs",
    "google sheets": "Google Sheets",
    "obsidian": "Obsidian",
    "telegram": "Telegram",
    "whatsapp": "WhatsApp",
    "vk": "VK",
    "вконтакте": "VK",
    "chatgpt": "ChatGPT",
    "claude": "Claude",
}

_PATH_RE = re.compile(r"[A-Za-z]:\\[^\n\"<>|*?]+")
_SPLIT_RE = re.compile(r"\s+[-—–]\s+")
_FILE_EXT = (".py", ".ts", ".tsx", ".js", ".jsx", ".md", ".json", ".txt", ".css", ".html", ".rs", ".go")

# Auto-created folders must stay short labels, not page/chat titles
_MAX_FOLDER_LEN = 28
_MAX_FOLDER_WORDS = 3
_SENTENCE_MARKERS = (
    " или ",
    " для ",
    " как ",
    " что ",
    " который ",
    " которая ",
    " this ",
    " that ",
    " with ",
    " from ",
)


def get_foreground_title() -> str:
    """Return the title of the currently focused window (Windows)."""
    if sys.platform != "win32":
        return ""
    import ctypes

    user32 = ctypes.windll.user32
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return ""
    length = user32.GetWindowTextLengthW(hwnd)
    if length <= 0:
        return ""
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value.strip()


def _strip_suffixes(title: str, suffixes: tuple[str, ...]) -> str:
    cleaned = title.strip()
    for suffix in suffixes:
        if cleaned.endswith(suffix):
            return cleaned[: -len(suffix)].rstrip()
    return cleaned


def _is_folder_worthy(name: str) -> bool:
    """Reject long page/chat titles used as folder names."""
    cleaned = name.strip()
    if len(cleaned) < 2 or len(cleaned) > _MAX_FOLDER_LEN:
        return False
    words = cleaned.split()
    if len(words) > _MAX_FOLDER_WORDS:
        return False
    padded = f" {cleaned.lower()} "
    if any(marker in padded for marker in _SENTENCE_MARKERS):
        return False
    return True


def extract_context_name(title: str) -> str | None:
    """
    One folder-worthy label from a window title.
    Examples:
      'Cool video - YouTube - Google Chrome' → 'YouTube'
      'main.py - CtrlNote - Cursor' → 'CtrlNote'
      long page title without a site → None (keep last folder)
    """
    if not title:
        return None

    raw = title.strip()
    if raw in {"CtrlNote", "Настройки CtrlNote"}:
        return None

    # Prefer known sites anywhere in the title (browser cases)
    lower = raw.lower()
    for key, canonical in sorted(_KNOWN_CONTEXTS.items(), key=lambda kv: -len(kv[0])):
        if re.search(rf"(?:^|[\s\-—–|/]){re.escape(key)}(?:$|[\s\-—–|/])", lower):
            return canonical

    cleaned = _strip_suffixes(raw, _BROWSER_SUFFIXES)
    cleaned = _strip_suffixes(cleaned, _EDITOR_SUFFIXES)

    # Paths → last meaningful folder
    for match in _PATH_RE.findall(raw):
        try:
            parts = [p for p in Path(match).parts if p not in {".", ".."}]
        except Exception:  # noqa: BLE001
            continue
        skip = {"users", "documents", "desktop", "downloads", "appdata", "проекты", "projects"}
        for part in reversed(parts):
            if re.fullmatch(r"[A-Za-z]:\\?", part):
                continue
            if part.lower() in skip:
                continue
            if part.lower().endswith(_FILE_EXT):
                continue
            if _is_folder_worthy(part):
                name = sanitize_filename(part, max_length=_MAX_FOLDER_LEN)
                if name:
                    return name

    parts = [p.strip() for p in _SPLIT_RE.split(cleaned) if p.strip()]
    for part in reversed(parts):
        low = part.lower()
        if low.endswith(_FILE_EXT):
            continue
        if low in {"untitled", "new tab", "new file", "readme"}:
            continue
        if not _is_folder_worthy(part):
            continue
        name = sanitize_filename(part, max_length=_MAX_FOLDER_LEN)
        if name and len(name) >= 2:
            return name

    return None


def extract_project_hints(title: str) -> list[str]:
    """Back-compat helper used by tests / soft matching."""
    name = extract_context_name(title)
    return [name] if name else []


def match_vault_folder(hints: list[str], folders: list[str]) -> str | None:
    """Return best matching existing vault-relative folder for hints."""
    candidates = [f.replace("\\", "/") for f in folders if f]
    if not hints or not candidates:
        return None

    for hint in hints:
        h = hint.strip().lower().replace("\\", "/")
        if not h:
            continue

        for folder in candidates:
            if folder.lower() == h:
                return folder

        hits = [f for f in candidates if Path(f).name.lower() == h]
        if hits:
            hits.sort(key=lambda f: (f.count("/"), len(f)))
            return hits[0]

        soft = [f for f in candidates if h in {p.lower() for p in f.split("/")}]
        if soft:
            soft.sort(key=lambda f: (f.count("/"), len(f)))
            return soft[0]

    return None


def resolve_folder(
    vault_path: str | Path,
    title: str | None = None,
    *,
    create: bool = True,
) -> str | None:
    """
    Find an existing vault folder for the active context, or create one at vault root.

    Returns vault-relative folder path (e.g. 'YouTube'), or None if no context.
    """
    win_title = title if title is not None else get_foreground_title()
    name = extract_context_name(win_title or "")
    if not name:
        return None

    vault = Path(vault_path).expanduser().resolve()
    if not vault.is_dir():
        return None

    folders = list_vault_folders(vault)
    matched = match_vault_folder([name], folders)
    if matched:
        return matched

    if not create:
        return name  # caller may create later

    folder_name = sanitize_filename(name, max_length=60)
    if not folder_name or folder_name in {".", ".."} or ".." in Path(folder_name).parts:
        return None
    try:
        target = resolve_under_vault(vault, folder_name)
    except VaultPathError:
        return None
    target.mkdir(parents=True, exist_ok=True)
    return folder_name.replace("\\", "/")


def suggest_folder(vault_folders: list[str], title: str | None = None) -> str | None:
    """Match only (no create) — kept for compatibility."""
    win_title = title if title is not None else get_foreground_title()
    if not win_title:
        return None
    if win_title.strip() in {"CtrlNote", "Настройки CtrlNote"}:
        return None
    hints = extract_project_hints(win_title)
    return match_vault_folder(hints, vault_folders)

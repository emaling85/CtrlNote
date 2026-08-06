"""Vault path containment — all note writes must stay under the vault root."""

from __future__ import annotations

from pathlib import Path


class VaultPathError(ValueError):
    """Raised when a path would escape the vault."""


def resolve_under_vault(vault_path: str | Path, *relative_parts: str) -> Path:
    """Join relative segments under vault and reject escapes / absolute segments.

    Empty parts are skipped. Each non-empty part must be a relative path without
    ``..`` components. The resolved result must stay inside ``vault.resolve()``.
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
        if part.is_absolute() or (len(part.parts) > 0 and part.parts[0] in {part.anchor, "/"}):
            # Windows: Path("C:/x").is_absolute() True; also reject UNC
            raise VaultPathError(f"Absolute path not allowed under vault: {raw!r}")
        if ".." in part.parts:
            raise VaultPathError(f"Parent traversal not allowed under vault: {raw!r}")
        segments.extend(p for p in part.parts if p not in {"", "."})

    target = vault.joinpath(*segments).resolve() if segments else vault
    try:
        target.relative_to(vault)
    except ValueError as exc:
        raise VaultPathError(f"Path escapes vault: {target} not under {vault}") from exc
    return target


def safe_attachment_name(name: str) -> str:
    """Keep only the final path component (no directories / traversal)."""
    base = Path(str(name).replace("\\", "/")).name
    if not base or base in {".", ".."}:
        raise VaultPathError(f"Invalid attachment name: {name!r}")
    if ".." in base:
        raise VaultPathError(f"Invalid attachment name: {name!r}")
    return base

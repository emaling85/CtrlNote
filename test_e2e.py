"""End-to-end smoke: configure vault, save note via CaptureWindow helpers."""

from __future__ import annotations

import tempfile
from pathlib import Path

from config import load_config, save_config
from note_saver import save_note


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        vault = Path(tmp) / "Vault"
        (vault / "Projects" / "Demo").mkdir(parents=True)
        (vault / "Inbox").mkdir()

        save_config(
            {
                "vault_path": str(vault),
                "hotkey": "ctrl+alt+n",
                "last_folder": "Projects/Demo",
            }
        )
        cfg = load_config()
        assert Path(cfg["vault_path"]) == vault.resolve() or Path(cfg["vault_path"]) == vault

        path = save_note(
            "Интеграционный тест\nПроверка CtrlNote MVP",
            cfg["vault_path"],
            cfg["last_folder"],
        )
        assert path.exists(), path
        text = path.read_text(encoding="utf-8")
        assert "Проверка CtrlNote MVP" in text
        print(f"OK saved: {path}")
        print(f"OK content length: {len(text)}")

        # Import GUI modules (create window briefly)
        import customtkinter as ctk

        from capture_window import CaptureWindow

        win = CaptureWindow()
        assert win.ensure_vault() is True
        win._refresh_folders()
        labels = list(win._folder_map.keys())
        assert "(корень vault)" in labels
        assert "Projects/Demo" in labels or "Projects\\Demo" in labels or any(
            "Demo" in x for x in labels
        )
        print(f"OK folders: {labels}")
        win.quit()
        print("E2E smoke passed")


if __name__ == "__main__":
    main()

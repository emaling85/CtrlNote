"""
Мастер первого запуска CtrlNote.

Помогает выбрать vault Obsidian, горячую клавишу и режим голоса.
"""

from __future__ import annotations

from tkinter import filedialog, messagebox
from typing import Callable

import customtkinter as ctk

from autostart import is_autostart_enabled, set_autostart
from config import is_configured, load_config, save_config


def run_onboarding(
    parent: ctk.CTk | ctk.CTkToplevel,
    *,
    on_done: Callable[[], None] | None = None,
) -> ctk.CTkToplevel:
    """Показывает короткий мастер настройки. После сохранения вызывает on_done.

    Возвращает окно диалога — вызывающий код может ждать его закрытия.
    """
    if parent.state() == "withdrawn":
        parent.deiconify()
        parent.lift()

    dialog = ctk.CTkToplevel(parent)
    dialog.title("CtrlNote Setup")
    dialog.geometry("520x420")
    dialog.minsize(480, 380)
    dialog.attributes("-topmost", True)
    dialog.transient(parent)
    dialog.grab_set()
    dialog.focus_force()
    dialog.lift()
    from ui_icon import apply_window_icon

    apply_window_icon(dialog)

    config = load_config()
    step = {"n": 0}  # номер текущего шага мастера (0, 1, 2)

    vault_var = ctk.StringVar(value=str(config.get("vault_path", "")))
    hotkey_var = ctk.StringVar(value=str(config.get("hotkey", "ctrl+alt+n")))
    autostart_var = ctk.BooleanVar(value=is_autostart_enabled() or bool(config.get("autostart")))
    engine_var = ctk.StringVar(value=str(config.get("voice_engine", "local")))

    body = ctk.CTkFrame(dialog, fg_color="transparent")
    body.pack(fill="both", expand=True, padx=20, pady=(20, 0))

    title = ctk.CTkLabel(body, text="", font=ctk.CTkFont(size=18, weight="bold"))
    title.pack(anchor="w")
    subtitle = ctk.CTkLabel(
        body,
        text="",
        text_color="gray60",
        wraplength=460,
        justify="left",
        anchor="w",
    )
    subtitle.pack(anchor="w", pady=(6, 16))

    content = ctk.CTkFrame(body, fg_color="transparent")
    content.pack(fill="both", expand=True)

    footer = ctk.CTkFrame(dialog, fg_color="transparent")
    footer.pack(fill="x", padx=20, pady=16)
    back_btn = ctk.CTkButton(footer, text="Back", width=90)
    next_btn = ctk.CTkButton(footer, text="Next", width=120)
    back_btn.pack(side="left")
    next_btn.pack(side="right")

    def clear_content() -> None:
        """Очищает область шага перед отрисовкой следующего."""
        for child in content.winfo_children():
            child.destroy()

    def render() -> None:
        """Рисует текущий шаг мастера (vault / хоткей / голос)."""
        clear_content()
        n = step["n"]
        back_btn.configure(state="normal" if n > 0 else "disabled")
        next_btn.configure(text="Done" if n == 2 else "Next")

        if n == 0:
            title.configure(text="Where should notes be saved?")
            subtitle.configure(
                text="Choose your Obsidian vault folder — a normal folder on disk "
                "that contains your .md files."
            )
            row = ctk.CTkFrame(content, fg_color="transparent")
            row.pack(fill="x")
            ctk.CTkEntry(row, textvariable=vault_var).pack(
                side="left", fill="x", expand=True, padx=(0, 8)
            )

            def browse() -> None:
                path = filedialog.askdirectory(
                    title="Select Obsidian vault",
                    parent=dialog,
                )
                if path:
                    vault_var.set(path)

            ctk.CTkButton(row, text="Browse", width=80, command=browse).pack(side="right")

        elif n == 1:
            title.configure(text="Hotkey")
            subtitle.configure(
                text="Default is Ctrl+Alt+N — to avoid conflicting with Ctrl+N in other apps. "
                "Format: ctrl+alt+n"
            )
            ctk.CTkEntry(content, textvariable=hotkey_var).pack(fill="x")
            ctk.CTkCheckBox(
                content,
                text="Start with Windows",
                variable=autostart_var,
            ).pack(anchor="w", pady=(16, 0))

        else:
            title.configure(text="Voice (optional)")
            subtitle.configure(
                text="Local Whisper works offline (the model downloads on first use). "
                "OpenAI is faster and needs an API key in Settings."
            )
            ctk.CTkOptionMenu(
                content,
                variable=engine_var,
                values=["local", "openai"],
                width=180,
            ).pack(anchor="w")
            ctk.CTkLabel(
                content,
                text="You can change everything later in Settings.",
                text_color="gray60",
            ).pack(anchor="w", pady=(16, 0))

    def finish() -> None:
        """Проверяет данные, сохраняет настройки и закрывает мастер."""
        vault = vault_var.get().strip()
        if not vault:
            messagebox.showwarning("CtrlNote", "Please choose a vault folder.", parent=dialog)
            step["n"] = 0
            render()
            return

        from pathlib import Path

        if not Path(vault).expanduser().is_dir():
            messagebox.showerror("CtrlNote", "Vault folder not found.", parent=dialog)
            step["n"] = 0
            render()
            return

        config["vault_path"] = vault
        config["hotkey"] = hotkey_var.get().strip().lower() or "ctrl+alt+n"
        config["voice_engine"] = engine_var.get().strip() or "local"
        want_autostart = bool(autostart_var.get())
        try:
            set_autostart(want_autostart)
        except OSError as exc:
            messagebox.showerror(
                "CtrlNote",
                f"Could not configure autostart:\n{exc}",
                parent=dialog,
            )
            return
        config["autostart"] = want_autostart
        save_config(config)
        dialog.destroy()
        if on_done:
            on_done()

    def go_next() -> None:
        """Кнопка «Далее» / «Готово»."""
        if step["n"] == 0:
            if not vault_var.get().strip():
                messagebox.showwarning(
                    "CtrlNote",
                    "Please select an Obsidian vault folder first.",
                    parent=dialog,
                )
                return
            step["n"] = 1
            render()
            return
        if step["n"] == 1:
            step["n"] = 2
            render()
            return
        finish()

    def go_back() -> None:
        """Кнопка «Назад»."""
        if step["n"] > 0:
            step["n"] -= 1
            render()

    back_btn.configure(command=go_back)
    next_btn.configure(command=go_next)
    dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
    render()
    return dialog


def needs_onboarding() -> bool:
    """Нужен ли мастер: True, если vault ещё не настроен."""
    return not is_configured()

"""First-run setup wizard for CtrlNote."""

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
    """Show a short setup wizard. Calls on_done after successful save.

    Returns the dialog so the caller can ``wait_window(dialog)``.
    """
    if parent.state() == "withdrawn":
        parent.deiconify()
        parent.lift()

    dialog = ctk.CTkToplevel(parent)
    dialog.title("Настройка CtrlNote")
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
    step = {"n": 0}

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
    back_btn = ctk.CTkButton(footer, text="Назад", width=90)
    next_btn = ctk.CTkButton(footer, text="Далее", width=120)
    back_btn.pack(side="left")
    next_btn.pack(side="right")

    def clear_content() -> None:
        for child in content.winfo_children():
            child.destroy()

    def render() -> None:
        clear_content()
        n = step["n"]
        back_btn.configure(state="normal" if n > 0 else "disabled")
        next_btn.configure(text="Готово" if n == 2 else "Далее")

        if n == 0:
            title.configure(text="Куда сохранять заметки?")
            subtitle.configure(
                text="Выберите папку vault Obsidian — обычная папка на диске, "
                "где лежат ваши .md файлы."
            )
            row = ctk.CTkFrame(content, fg_color="transparent")
            row.pack(fill="x")
            ctk.CTkEntry(row, textvariable=vault_var).pack(
                side="left", fill="x", expand=True, padx=(0, 8)
            )

            def browse() -> None:
                path = filedialog.askdirectory(
                    title="Выберите vault Obsidian",
                    parent=dialog,
                )
                if path:
                    vault_var.set(path)

            ctk.CTkButton(row, text="Обзор", width=80, command=browse).pack(side="right")

        elif n == 1:
            title.configure(text="Горячая клавиша")
            subtitle.configure(
                text="По умолчанию Ctrl+Alt+N — чтобы не конфликтовать с Ctrl+N в других программах. "
                "Формат: ctrl+alt+n"
            )
            ctk.CTkEntry(content, textvariable=hotkey_var).pack(fill="x")
            ctk.CTkCheckBox(
                content,
                text="Запускать вместе с Windows",
                variable=autostart_var,
            ).pack(anchor="w", pady=(16, 0))

        else:
            title.configure(text="Голос (по желанию)")
            subtitle.configure(
                text="Локальный Whisper работает без интернета (модель скачается при первом использовании). "
                "OpenAI — быстрее, нужен API-ключ в настройках ⚙."
            )
            ctk.CTkOptionMenu(
                content,
                variable=engine_var,
                values=["local", "openai"],
                width=180,
            ).pack(anchor="w")
            ctk.CTkLabel(
                content,
                text="Позже всё можно изменить в ⚙ Настройки.",
                text_color="gray60",
            ).pack(anchor="w", pady=(16, 0))

    def finish() -> None:
        vault = vault_var.get().strip()
        if not vault:
            messagebox.showwarning("CtrlNote", "Укажите папку vault.", parent=dialog)
            step["n"] = 0
            render()
            return

        from pathlib import Path

        if not Path(vault).expanduser().is_dir():
            messagebox.showerror("CtrlNote", "Папка vault не найдена.", parent=dialog)
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
                f"Не удалось настроить автозапуск:\n{exc}",
                parent=dialog,
            )
            return
        config["autostart"] = want_autostart
        save_config(config)
        dialog.destroy()
        if on_done:
            on_done()

    def go_next() -> None:
        if step["n"] == 0:
            if not vault_var.get().strip():
                messagebox.showwarning(
                    "CtrlNote",
                    "Сначала выберите папку vault Obsidian.",
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
        if step["n"] > 0:
            step["n"] -= 1
            render()

    back_btn.configure(command=go_back)
    next_btn.configure(command=go_next)
    dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
    render()
    return dialog


def needs_onboarding() -> bool:
    return not is_configured()

"""
Мастер первого запуска CtrlNote.

Шаги: язык → vault Obsidian → горячая клавиша → голос.
Показывается один раз — пока vault не настроен.
"""

from __future__ import annotations

from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Callable

import customtkinter as ctk

from autostart import is_autostart_enabled, set_autostart
from config import CONFIG_PATH, is_configured, load_config, save_config
from i18n import detect_system_language, get_language, set_language, t

LAST_STEP = 3


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
    dialog.geometry("540x430")
    dialog.minsize(500, 400)
    dialog.attributes("-topmost", True)
    dialog.transient(parent)
    dialog.grab_set()
    dialog.focus_force()
    dialog.lift()
    from ui_icon import apply_window_icon

    apply_window_icon(dialog)

    config = load_config()
    # Совсем новый пользователь — подставляем язык Windows; иначе тот, что уже выбран
    if not CONFIG_PATH.exists():
        set_language(detect_system_language())
    step = {"n": 0}  # номер текущего шага мастера (0..3)

    vault_var = ctk.StringVar(value=str(config.get("vault_path", "")))
    hotkey_var = ctk.StringVar(value=str(config.get("hotkey", "ctrl+alt+n")))
    autostart_var = ctk.BooleanVar(value=is_autostart_enabled() or bool(config.get("autostart")))
    engine_var = ctk.StringVar(value=str(config.get("voice_engine", "local")))

    body = ctk.CTkFrame(dialog, fg_color="transparent")
    body.pack(fill="both", expand=True, padx=22, pady=(22, 0))

    title = ctk.CTkLabel(body, text="", font=ctk.CTkFont(size=19, weight="bold"))
    title.pack(anchor="w")
    subtitle = ctk.CTkLabel(body, text="", text_color="gray60", wraplength=480, justify="left", anchor="w")
    subtitle.pack(anchor="w", pady=(6, 18))

    content = ctk.CTkFrame(body, fg_color="transparent")
    content.pack(fill="both", expand=True)

    footer = ctk.CTkFrame(dialog, fg_color="transparent")
    footer.pack(fill="x", padx=22, pady=16)
    back_btn = ctk.CTkButton(footer, width=90)
    next_btn = ctk.CTkButton(footer, width=120)
    back_btn.pack(side="left")
    next_btn.pack(side="right")

    def choose_language(code: str) -> None:
        set_language(code)
        render()

    def render() -> None:
        """Рисует текущий шаг мастера."""
        for child in content.winfo_children():
            child.destroy()
        n = step["n"]
        dialog.title(t("onboard_title"))
        back_btn.configure(text=t("onboard_back"), state="normal" if n > 0 else "disabled")
        next_btn.configure(text=t("onboard_done") if n == LAST_STEP else t("onboard_next"))

        if n == 0:
            title.configure(text=t("onboard_lang_title"))
            subtitle.configure(text=t("onboard_lang_sub"))
            row = ctk.CTkFrame(content, fg_color="transparent")
            row.pack(fill="x")
            for code, label in (("en", "English"), ("ru", "Русский")):
                on = get_language() == code
                ctk.CTkButton(
                    row,
                    text=label,
                    height=64,
                    corner_radius=12,
                    font=ctk.CTkFont(size=17, weight="bold"),
                    fg_color="#3878fa" if on else "#2a2a2a",
                    hover_color="#2f66d8" if on else "#353535",
                    border_width=2,
                    border_color="#6b9bff" if on else "#3a3a3a",
                    command=lambda c=code: choose_language(c),
                ).pack(side="left", expand=True, fill="x", padx=(0, 10) if code == "en" else (0, 0))

        elif n == 1:
            title.configure(text=t("onboard_vault_title"))
            subtitle.configure(text=t("onboard_vault_sub"))
            row = ctk.CTkFrame(content, fg_color="transparent")
            row.pack(fill="x")
            ctk.CTkEntry(row, textvariable=vault_var).pack(side="left", fill="x", expand=True, padx=(0, 8))

            def browse() -> None:
                path = filedialog.askdirectory(title=t("select_vault"), parent=dialog)
                if path:
                    vault_var.set(path)

            ctk.CTkButton(row, text=t("browse"), width=90, command=browse).pack(side="right")

        elif n == 2:
            title.configure(text=t("onboard_hotkey_title"))
            subtitle.configure(text=t("onboard_hotkey_sub"))
            ctk.CTkEntry(content, textvariable=hotkey_var).pack(fill="x")
            ctk.CTkCheckBox(content, text=t("start_windows"), variable=autostart_var).pack(anchor="w", pady=(16, 0))

        else:
            title.configure(text=t("onboard_voice_title"))
            subtitle.configure(text=t("onboard_voice_sub"))
            ctk.CTkOptionMenu(content, variable=engine_var, values=["local", "openai"], width=180).pack(anchor="w")
            from edition import is_trader

            notes = [t("onboard_later")]
            if is_trader():
                notes.insert(0, t("onboard_trade_note"))
            for text in notes:
                ctk.CTkLabel(
                    content, text=text, text_color="gray60", wraplength=480, justify="left", anchor="w"
                ).pack(anchor="w", pady=(14, 0))

    def vault_ok() -> bool:
        vault = vault_var.get().strip()
        if not vault or not Path(vault).expanduser().is_dir():
            messagebox.showwarning("CtrlNote", t("pick_vault_warn"), parent=dialog)
            step["n"] = 1
            render()
            return False
        return True

    def finish() -> None:
        """Проверяет данные, сохраняет настройки и закрывает мастер."""
        if not vault_ok():
            return
        want_autostart = bool(autostart_var.get())
        try:
            set_autostart(want_autostart)
        except OSError as exc:
            messagebox.showerror("CtrlNote", t("autostart_error", exc=exc), parent=dialog)
            return
        config["ui_language"] = get_language()
        config["vault_path"] = vault_var.get().strip()
        config["hotkey"] = hotkey_var.get().strip().lower() or "ctrl+alt+n"
        config["voice_engine"] = engine_var.get().strip() or "local"
        config["autostart"] = want_autostart
        save_config(config)
        dialog.destroy()
        if on_done:
            on_done()

    def go_next() -> None:
        """Кнопка «Далее» / «Готово»."""
        if step["n"] == 1 and not vault_ok():
            return
        if step["n"] < LAST_STEP:
            step["n"] += 1
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

"""
Окно быстрой заметки CtrlNote.

Появляется по горячей клавише или из трея: текст, голос, картинки, шаблоны, сохранение в vault.
"""

from __future__ import annotations

import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import messagebox
from typing import Callable

import customtkinter as ctk
from PIL import Image

from config import is_configured, load_config, save_config
from templates import NONE_LABEL, get_template_by_name, load_templates, template_names


class CaptureWindow:
    """Всплывающее окно поверх других программ для быстрого ввода заметки."""

    def __init__(
        self,
        on_saved: Callable[[str], None] | None = None,
        on_hotkey_changed: Callable[[], None] | None = None,
    ) -> None:
        self.on_saved = on_saved
        self.on_hotkey_changed = on_hotkey_changed

        # Тема до создания окна — быстрее первая отрисовка.
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        self.root = ctk.CTk()
        # Сразу прячем, чтобы при сборке UI не мигало пустое окно.
        self.root.withdraw()
        self.root.title("CtrlNote")
        self.root.geometry("560x400")
        self.root.minsize(480, 320)
        self.root.attributes("-topmost", True)
        self.root.protocol("WM_DELETE_WINDOW", self.hide)

        # Переменные интерфейса: выбранная папка, шаблон, статусная строка
        self.folder_var = ctk.StringVar(value="(корень vault)")
        self.template_var = ctk.StringVar(value=NONE_LABEL)
        self.status_var = ctk.StringVar(value="")
        self._folder_map: dict[str, str] = {"(корень vault)": ""}
        self._visible = False
        self._show_gen = 0
        self._pending_images: list[tuple[str, Image.Image]] = []  # картинки до сохранения
        self._recorder = None  # текущая запись с микрофона
        self._voice_busy = False
        self._pending_context_title: str | None = None  # заголовок окна до фокуса CtrlNote
        self._last_voice_start: str | None = None
        self._last_voice_end: str | None = None

        self._build_ui()
        self.root.bind("<Escape>", lambda _e: self.hide())
        self.root.bind("<Control-Return>", lambda _e: self._save())
        self.root.bind("<Control-KP_Enter>", lambda _e: self._save())
        self._bind_paste_shortcuts()
        # Горячие клавиши markdown подключим чуть позже — не нужны на первом кадре.
        self.root.after_idle(self._bind_markdown_shortcuts)

    def _bind_markdown_shortcuts(self) -> None:
        from markdown_edit import bind_markdown_shortcuts

        bind_markdown_shortcuts(self.root, self.text)

    def _build_ui(self) -> None:
        """Собирает элементы окна: папка, кнопки, текст, подвал."""
        # Тёмный спокойный фон
        self.root.configure(fg_color="#1a1a1a")

        # Верхняя строка: выбор папки vault и кнопки (настройки, рисунок, микрофон)
        top = ctk.CTkFrame(self.root, fg_color="transparent")
        top.pack(fill="x", padx=14, pady=(12, 6))

        self.folder_menu = ctk.CTkOptionMenu(
            top,
            variable=self.folder_var,
            values=["(корень vault)"],
            width=220,
            height=28,
            fg_color="#2a2a2a",
            button_color="#333333",
            button_hover_color="#3a3a3a",
        )
        self.folder_menu.pack(side="left", fill="x", expand=True)

        icon_kwargs = {
            "width": 32,
            "height": 28,
            "fg_color": "transparent",
            "hover_color": "#2f2f2f",
            "text_color": "#c8c8c8",
        }
        ctk.CTkButton(top, text="⚙", command=self.open_settings, **icon_kwargs).pack(
            side="right", padx=(4, 0)
        )
        self.paint_btn = ctk.CTkButton(top, text="✎", command=self.open_paint, **icon_kwargs)
        self.paint_btn.pack(side="right", padx=(4, 0))
        self.mic_btn = ctk.CTkButton(top, text="🎙", command=self._toggle_voice, **icon_kwargs)
        self.mic_btn.pack(side="right", padx=(4, 0))

        # Выбор шаблона заметки
        mid = ctk.CTkFrame(self.root, fg_color="transparent")
        mid.pack(fill="x", padx=14, pady=(0, 6))
        # Имена шаблонов подтянем при первом показе — без чтения диска при сборке UI.
        self.template_menu = ctk.CTkOptionMenu(
            mid,
            variable=self.template_var,
            values=[NONE_LABEL],
            width=180,
            height=28,
            command=self._on_template_chosen,
            fg_color="#2a2a2a",
            button_color="#333333",
            button_hover_color="#3a3a3a",
        )
        self.template_menu.pack(side="left")

        # Основное поле ввода текста заметки
        self.text = ctk.CTkTextbox(
            self.root,
            font=ctk.CTkFont(size=14),
            wrap="word",
            fg_color="#141414",
            border_color="#2a2a2a",
            border_width=1,
        )
        self.text.pack(fill="both", expand=True, padx=14, pady=(0, 8))

        # Нижняя панель: вставка, шаблоны, отмена, сохранить
        footer = ctk.CTkFrame(self.root, fg_color="transparent")
        footer.pack(fill="x", padx=14, pady=(0, 6))

        ghost = {
            "width": 72,
            "height": 30,
            "fg_color": "transparent",
            "hover_color": "#2f2f2f",
            "text_color": "#aaaaaa",
            "border_width": 0,
        }
        ctk.CTkButton(footer, text="Вставить", command=self._paste_from_clipboard, **ghost).pack(
            side="left"
        )
        ctk.CTkButton(footer, text="Шаблоны", command=self.open_templates_manager, **ghost).pack(
            side="left", padx=(4, 0)
        )
        self.redo_voice_btn = ctk.CTkButton(
            footer,
            text="↻ Голос",
            command=self._redo_voice,
            state="disabled",
            **ghost,
        )
        self.redo_voice_btn.pack(side="left", padx=(4, 0))

        ctk.CTkButton(
            footer,
            text="Отмена",
            width=80,
            height=30,
            fg_color="transparent",
            hover_color="#2f2f2f",
            text_color="#888888",
            command=self.hide,
        ).pack(side="right")
        ctk.CTkButton(
            footer,
            text="Сохранить",
            width=110,
            height=30,
            fg_color="#3878fa",
            hover_color="#2f66d8",
            command=self._save,
        ).pack(side="right", padx=(0, 6))

        ctk.CTkLabel(
            self.root,
            textvariable=self.status_var,
            text_color="#666666",
            font=ctk.CTkFont(size=11),
            anchor="w",
        ).pack(fill="x", padx=14, pady=(0, 10))

    def _bind_paste_shortcuts(self) -> None:
        """Вешает Ctrl+V, Shift+Insert и правый клик «Вставить» на поле текста."""

        def on_paste(_event: tk.Event | None = None) -> str:
            self._paste_from_clipboard()
            return "break"

        def on_context_menu(event: tk.Event) -> str:
            menu = tk.Menu(self.root, tearoff=0)
            menu.add_command(label="Вставить", command=self._paste_from_clipboard)
            menu.add_command(label="Копировать", command=self._copy_selection)
            menu.add_command(label="Вырезать", command=self._cut_selection)
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()
            return "break"

        inner = getattr(self.text, "_textbox", None)
        targets: list = [self.root, self.text]
        if inner is not None:
            targets.append(inner)

        for widget in targets:
            for sequence in ("<Control-v>", "<Control-V>", "<Shift-Insert>"):
                widget.bind(sequence, on_paste, add="+")
            widget.bind("<<Paste>>", on_paste, add="+")

        # Правый клик удобнее на внутреннем tk.Text
        if inner is not None:
            inner.bind("<Button-3>", on_context_menu, add="+")
        self.text.bind("<Button-3>", on_context_menu, add="+")

    def _copy_selection(self) -> None:
        """Копирует выделенный текст в буфер обмена."""
        try:
            selected = self.text.get("sel.first", "sel.last")
        except tk.TclError:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(selected)

    def _cut_selection(self) -> None:
        """Вырезает выделенный текст."""
        self._copy_selection()
        try:
            self.text.delete("sel.first", "sel.last")
        except tk.TclError:
            pass

    def _insert_at_cursor(self, text: str) -> None:
        """Вставляет текст в позицию курсора (заменяя выделение)."""
        try:
            self.text.delete("sel.first", "sel.last")
        except tk.TclError:
            pass
        self.text.insert("insert", text)
        self.text.focus_set()

    def _paste_from_clipboard(self) -> None:
        """Вставка из буфера: сначала картинка, потом файлы, потом текст."""
        # Порядок: скриншот/картинка → список файлов → обычный текст
        from PIL import ImageGrab

        clipped = ImageGrab.grabclipboard()
        if isinstance(clipped, Image.Image):
            self._paste_image(clipped.copy())
            return

        if isinstance(clipped, list):
            pasted_any = False
            for item in clipped:
                path = Path(str(item))
                if path.is_file() and path.suffix.lower() in {
                    ".png",
                    ".jpg",
                    ".jpeg",
                    ".gif",
                    ".webp",
                    ".bmp",
                }:
                    try:
                        with Image.open(path) as img:
                            self._paste_image(img.copy(), preferred_name=path.name)
                        pasted_any = True
                    except OSError:
                        continue
            if pasted_any:
                return

        try:
            text = self.root.clipboard_get()
        except tk.TclError:
            self.status_var.set("Буфер обмена пуст")
            return

        if not text:
            self.status_var.set("Буфер обмена пуст")
            return

        self._insert_at_cursor(text)
        self.status_var.set("")

    def _paste_image(self, image: Image.Image, preferred_name: str | None = None) -> None:
        """Кладёт картинку в очередь вложений и вставляет ![[имя]] в текст."""
        stamp = datetime.now().strftime("%Y%m%d%H%M%S")
        if preferred_name:
            name = preferred_name
            existing = {n for n, _ in self._pending_images}
            if name in existing:
                stem = Path(name).stem
                suffix = Path(name).suffix or ".png"
                index = 2
                while f"{stem} ({index}){suffix}" in existing:
                    index += 1
                name = f"{stem} ({index}){suffix}"
        else:
            name = f"Pasted image {stamp}.png"

        if Path(name).suffix.lower() != ".png":
            name = f"{Path(name).stem}.png"

        self._pending_images.append((name, image))
        markdown = f"![[{name}]]"
        try:
            current = self.text.get("insert linestart", "insert")
            prefix = "" if current == "" or current.endswith("\n") else "\n"
        except tk.TclError:
            prefix = "\n"
        self._insert_at_cursor(f"{prefix}{markdown}\n")
        self.status_var.set("")

    def open_paint(self) -> None:
        """Открывает окно рисования и добавляет рисунок как картинку в заметку."""
        if self.root.state() == "withdrawn":
            self.root.deiconify()
            self.root.lift()

        from paint_window import drawing_filename, open_paint

        def on_done(image: Image.Image) -> None:
            self._paste_image(image, preferred_name=drawing_filename())
            self.status_var.set("Рисунок добавлен")

        open_paint(self.root, on_done=on_done)

    def _toggle_voice(self) -> None:
        """Старт/стоп записи голоса по кнопке микрофона."""
        if self._voice_busy:
            return
        if self._recorder is not None and self._recorder.recording:
            self._stop_voice_and_transcribe()
        else:
            self._start_voice()

    def _redo_voice(self) -> None:
        """Удаляет последнюю голосовую вставку и сразу пишет заново."""
        if self._voice_busy:
            return
        if self._last_voice_start and self._last_voice_end:
            try:
                self.text.delete(self._last_voice_start, self._last_voice_end)
            except tk.TclError:
                pass
        self._last_voice_start = None
        self._last_voice_end = None
        self.redo_voice_btn.configure(state="disabled")
        self._start_voice()

    def _start_voice(self) -> None:
        """Включает микрофон и меняет кнопку на «стоп»."""
        try:
            from voice import MicRecorder
        except ImportError:
            messagebox.showerror(
                "CtrlNote",
                "Голосовые зависимости не установлены.",
                parent=self.root,
            )
            return
        try:
            self._recorder = MicRecorder()
            self._recorder.start()
        except Exception as exc:  # noqa: BLE001
            self._recorder = None
            messagebox.showerror(
                "CtrlNote",
                f"Не удалось открыть микрофон:\n{exc}",
                parent=self.root,
            )
            return
        self.mic_btn.configure(text="⏹", fg_color="#b33a3a", hover_color="#992f2f")
        self.redo_voice_btn.configure(state="disabled")
        self.status_var.set("Запись…")

    def _stop_voice_and_transcribe(self) -> None:
        """Останавливает запись и запускает расшифровку в фоне."""
        if self._recorder is None:
            return
        try:
            audio = self._recorder.stop()
        except Exception as exc:  # noqa: BLE001
            self._recorder = None
            self.mic_btn.configure(text="🎙", fg_color="transparent", hover_color=("gray75", "gray30"))
            messagebox.showerror("CtrlNote", f"Ошибка записи:\n{exc}", parent=self.root)
            return

        self._recorder = None
        self.mic_btn.configure(text="…", state="disabled", fg_color="transparent")
        self._voice_busy = True
        self.status_var.set("Расшифровка…")

        from voice import RecordingResult, model_likely_cached, transcribe_in_background
        from config import load_config as _load

        cfg = _load()
        if cfg.get("voice_engine") != "openai":
            model = str(cfg.get("whisper_model", "small"))
            if not model_likely_cached(model):
                self.status_var.set("Скачивание модели…")

        def on_progress(message: str) -> None:
            self.root.after(0, lambda m=message: self.status_var.set(m))

        def on_done(result: RecordingResult) -> None:
            self.root.after(0, lambda: self._on_voice_done(result))

        def on_error(exc: BaseException) -> None:
            self.root.after(0, lambda: self._on_voice_error(exc))

        transcribe_in_background(
            audio,
            on_done=on_done,
            on_error=on_error,
            on_progress=on_progress,
        )

    def _on_voice_done(self, result) -> None:
        """Вставляет распознанный текст в заметку."""
        self._voice_busy = False
        self.mic_btn.configure(
            text="🎙",
            state="normal",
            fg_color="transparent",
            hover_color=("gray75", "gray30"),
        )
        if result.text:
            prefix = ""
            try:
                current = self.text.get("insert linestart", "insert")
                if current and not current.endswith("\n") and self.text.get("1.0", "end-1c").strip():
                    prefix = "\n"
            except tk.TclError:
                prefix = "\n"
            chunk = f"{prefix}{result.text}\n"
            start = self.text.index("insert")
            self._insert_at_cursor(chunk)
            end = self.text.index("insert")
            self._last_voice_start = start
            self._last_voice_end = end
            self.redo_voice_btn.configure(state="normal")
            self.status_var.set("")
        else:
            self.status_var.set("Ничего не распознано")
            self.redo_voice_btn.configure(state="disabled")

    def _on_voice_error(self, exc: BaseException) -> None:
        """Показывает ошибку расшифровки пользователю."""
        self._voice_busy = False
        self.mic_btn.configure(
            text="🎙",
            state="normal",
            fg_color="transparent",
            hover_color=("gray75", "gray30"),
        )
        self.status_var.set("Ошибка расшифровки")
        messagebox.showerror("CtrlNote", f"Не удалось расшифровать:\n{exc}", parent=self.root)

    def _cancel_voice(self) -> None:
        """Прерывает запись при закрытии окна."""
        if self._recorder is not None and self._recorder.recording:
            try:
                self._recorder.stop()
            except Exception:  # noqa: BLE001
                pass
            self._recorder = None
        self.mic_btn.configure(
            text="🎙",
            state="normal",
            fg_color="transparent",
            hover_color=("gray75", "gray30"),
        )

    def _center(self) -> None:
        """Ставит окно примерно по центру экрана."""
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        x = max(0, (screen_w - width) // 2)
        y = max(0, (screen_h - height) // 3)
        self.root.geometry(f"+{x}+{y}")

    def ensure_vault(self) -> bool:
        """Если vault не настроен — показывает мастер первичной настройки."""
        config = load_config()
        if is_configured(config):
            return True

        from onboarding import run_onboarding

        def on_done() -> None:
            if self.on_hotkey_changed:
                try:
                    self.on_hotkey_changed()
                except Exception:  # noqa: BLE001
                    pass

        dialog = run_onboarding(self.root, on_done=on_done)
        self.root.wait_window(dialog)
        return is_configured()

    def _refresh_folders(
        self,
        preferred_relative: str | None = None,
        folders: list[str] | None = None,
    ) -> None:
        """Обновляет список папок vault в выпадающем меню."""
        from note_saver import list_vault_folders

        config = load_config()
        vault = config.get("vault_path", "")
        if folders is None:
            folders = list_vault_folders(vault) if vault else [""]

        labels: list[str] = []
        self._folder_map.clear()
        for rel in folders:
            if rel == "":
                label = "(корень vault)"
            elif rel == "(корень vault)":
                # Чтобы не спутать с подписью корня vault
                label = "./(корень vault)"
            else:
                label = rel
            labels.append(label)
            self._folder_map[label] = rel

        self.folder_menu.configure(values=labels)

        selected = "(корень vault)"
        target = preferred_relative if preferred_relative is not None else config.get("last_folder", "")
        for label, rel in self._folder_map.items():
            if rel == target:
                selected = label
                break
        self.folder_var.set(selected)

    def _refresh_templates(self) -> None:
        """Обновляет список шаблонов."""
        names = template_names()
        self.template_menu.configure(values=names)
        current = self.template_var.get()
        if current not in names:
            self.template_var.set(NONE_LABEL)

    def _on_template_chosen(self, choice: str) -> None:
        """Подставляет текст выбранного шаблона в поле заметки."""
        if choice == NONE_LABEL:
            return
        tmpl = get_template_by_name(choice)
        if not tmpl:
            return
        existing = self.text.get("1.0", "end-1c")
        if existing.strip():
            if not messagebox.askyesno(
                "CtrlNote",
                "Заменить текст заметки шаблоном?",
                parent=self.root,
            ):
                self.template_var.set(NONE_LABEL)
                return
        self.text.delete("1.0", "end")
        self.text.insert("1.0", tmpl["body"])
        self.text.focus_set()

    def open_templates_manager(self) -> None:
        """Окно управления шаблонами: создать, править, удалить."""
        from templates import add_template, delete_template, update_template

        if self.root.state() == "withdrawn":
            self.root.deiconify()

        dialog = ctk.CTkToplevel(self.root)
        dialog.title("Шаблоны")
        dialog.geometry("520x420")
        dialog.minsize(480, 360)
        dialog.attributes("-topmost", True)
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.focus_force()
        from ui_icon import apply_window_icon

        apply_window_icon(dialog)

        templates = load_templates()
        names = [t["name"] for t in templates] or ["(пусто)"]
        selected_id = {"value": templates[0]["id"] if templates else ""}

        left = ctk.CTkFrame(dialog, fg_color="transparent")
        left.pack(side="left", fill="y", padx=(16, 8), pady=16)

        ctk.CTkLabel(left, text="Список").pack(anchor="w")
        list_var = ctk.StringVar(value=names[0])
        name_menu = ctk.CTkOptionMenu(left, variable=list_var, values=names, width=160)
        name_menu.pack(anchor="w", pady=(4, 12))

        right = ctk.CTkFrame(dialog, fg_color="transparent")
        right.pack(side="left", fill="both", expand=True, padx=(8, 16), pady=16)

        ctk.CTkLabel(right, text="Название").pack(anchor="w")
        name_var = ctk.StringVar(value=templates[0]["name"] if templates else "")
        name_entry = ctk.CTkEntry(right, textvariable=name_var)
        name_entry.pack(fill="x", pady=(4, 8))

        ctk.CTkLabel(right, text="Текст шаблона").pack(anchor="w")
        body_box = ctk.CTkTextbox(right, wrap="word")
        body_box.pack(fill="both", expand=True, pady=(4, 8))
        if templates:
            body_box.insert("1.0", templates[0]["body"])

        def current_templates() -> list[dict[str, str]]:
            return load_templates()

        def select_by_name(name: str) -> None:
            for item in current_templates():
                if item["name"] == name:
                    selected_id["value"] = item["id"]
                    name_var.set(item["name"])
                    body_box.delete("1.0", "end")
                    body_box.insert("1.0", item["body"])
                    return

        def reload_list(prefer_name: str | None = None) -> None:
            items = current_templates()
            values = [t["name"] for t in items] or ["(пусто)"]
            name_menu.configure(values=values)
            pick = prefer_name if prefer_name in values else values[0]
            list_var.set(pick)
            if items and pick != "(пусто)":
                select_by_name(pick)
            else:
                selected_id["value"] = ""
                name_var.set("")
                body_box.delete("1.0", "end")

        def on_pick(choice: str) -> None:
            if choice == "(пусто)":
                return
            select_by_name(choice)

        name_menu.configure(command=on_pick)

        def on_new() -> None:
            item = add_template("Новый шаблон", "# Заголовок\n\n")
            reload_list(item["name"])
            self._refresh_templates()

        def on_save() -> None:
            tid = selected_id["value"]
            name = name_var.get().strip()
            body = body_box.get("1.0", "end-1c")
            if not name:
                messagebox.showwarning("CtrlNote", "Укажите название шаблона", parent=dialog)
                return
            if not tid:
                item = add_template(name, body)
                reload_list(item["name"])
            else:
                update_template(tid, name, body)
                reload_list(name)
            self._refresh_templates()

        def on_delete() -> None:
            tid = selected_id["value"]
            if not tid:
                return
            if not messagebox.askyesno("CtrlNote", "Удалить шаблон?", parent=dialog):
                return
            delete_template(tid)
            reload_list()
            self._refresh_templates()

        btns = ctk.CTkFrame(left, fg_color="transparent")
        btns.pack(anchor="w", pady=(8, 0))
        ctk.CTkButton(btns, text="Новый", width=70, command=on_new).pack(pady=4)
        ctk.CTkButton(btns, text="Сохранить", width=70, command=on_save).pack(pady=4)
        ctk.CTkButton(btns, text="Удалить", width=70, command=on_delete).pack(pady=4)
        ctk.CTkButton(btns, text="Закрыть", width=70, command=dialog.destroy).pack(pady=(16, 4))

    def show(self) -> None:
        """Показывает окно заметки и подбирает папку по активному окну."""
        # Сначала запоминаем контекст — потом наше окно перехватит фокус
        context_title = self._pending_context_title
        self._pending_context_title = None
        if context_title is None:
            try:
                from context import get_foreground_title

                context_title = get_foreground_title()
            except Exception:  # noqa: BLE001
                context_title = ""

        if not self.ensure_vault():
            return

        # Сначала лёгкий сброс UI и показ окна — сканирование vault отложим.
        self.template_var.set(NONE_LABEL)
        self.text.delete("1.0", "end")
        self._pending_images.clear()
        self._last_voice_start = None
        self._last_voice_end = None
        self.redo_voice_btn.configure(state="disabled")
        self.status_var.set("")

        # Подставим папку из прошлой сессии без сканирования vault (безопасно, если сохранят сразу).
        config = load_config()
        last = str(config.get("last_folder", "") or "")
        self._folder_map = {"(корень vault)": ""}
        labels = ["(корень vault)"]
        if last:
            self._folder_map[last] = last
            labels.append(last)
        self.folder_menu.configure(values=labels)
        self.folder_var.set(last if last else "(корень vault)")

        self._show_gen += 1
        gen = self._show_gen
        self.root.deiconify()
        self.root.lift()
        self.root.attributes("-topmost", True)
        self.root.focus_force()
        self._center()
        self.text.focus_set()
        self._visible = True

        self.root.after(0, lambda: self._finish_show(gen, context_title or ""))

    def _finish_show(self, gen: int, context_title: str) -> None:
        """После показа окна: сканирует vault и подставляет папку по контексту."""
        if gen != self._show_gen or not self._visible:
            return

        from note_saver import list_vault_folders

        config = load_config()
        vault = config.get("vault_path", "")
        folders = list_vault_folders(vault) if vault else [""]
        preferred: str | None = None
        if config.get("auto_folder", True):
            try:
                from context import resolve_folder

                preferred = resolve_folder(
                    vault,
                    title=context_title,
                    create=True,
                    folders=folders,
                )
            except Exception:  # noqa: BLE001
                preferred = None

        if preferred and preferred not in folders:
            folders = [*folders, preferred]

        if gen != self._show_gen or not self._visible:
            return

        self._refresh_folders(preferred_relative=preferred, folders=folders)
        self._refresh_templates()

    def hide(self) -> None:
        """Прячет окно (программа продолжает жить в трее)."""
        self._show_gen += 1  # отменить отложенное завершение показа
        self._cancel_voice()
        self.root.withdraw()
        self._visible = False
        self._pending_images.clear()

    def toggle(self) -> None:
        """По горячей клавише: показать или скрыть окно."""
        if self._visible and self.root.state() == "normal":
            self.hide()
        else:
            # Сразу снимаем заголовок активного окна (до нашего фокуса)
            try:
                from context import get_foreground_title

                self._pending_context_title = get_foreground_title()
            except Exception:  # noqa: BLE001
                self._pending_context_title = ""
            self.show()

    def _save(self) -> None:
        """Сохраняет заметку в vault и закрывает окно."""
        content = self.text.get("1.0", "end").strip()
        if not content and not self._pending_images:
            self.status_var.set("Пустая заметка — нечего сохранять")
            return

        config = load_config()
        if not is_configured(config):
            if not self.ensure_vault():
                return
            config = load_config()

        if config.get("link_daily_note"):
            from daily_note import append_daily_link

            content = append_daily_link(
                content,
                fmt=str(config.get("daily_note_format", "YYYY-MM-DD")),
            ).strip()

        label = self.folder_var.get()
        relative = self._folder_map.get(label, "")
        try:
            from note_saver import save_note
            from vault_paths import VaultPathError

            path = save_note(
                content or f"Вставка {datetime.now().strftime('%Y-%m-%d %H-%M')}",
                config["vault_path"],
                relative,
                attachments=list(self._pending_images),
            )
        except (OSError, VaultPathError, ValueError) as exc:
            messagebox.showerror("CtrlNote", f"Не удалось сохранить:\n{exc}", parent=self.root)
            return

        if config.get("append_daily_note"):
            try:
                from daily_note import append_to_daily_file
                from note_saver import title_from_content_line
                from vault_paths import VaultPathError

                first = next((ln.strip() for ln in content.splitlines() if ln.strip()), path.stem)
                title = title_from_content_line(first) or path.stem
                append_to_daily_file(
                    config["vault_path"],
                    title,
                    folder=str(config.get("daily_note_folder", "") or ""),
                    fmt=str(config.get("daily_note_format", "YYYY-MM-DD")),
                )
            except (OSError, VaultPathError, ValueError):
                pass

        config["last_folder"] = relative
        save_config(config)

        if self.on_saved:
            self.on_saved(str(path))
        self.status_var.set(f"Сохранено: {path.name}")
        self._pending_images.clear()
        self.hide()

    def open_settings(self) -> None:
        """Окно настроек: vault, хоткей, автозапуск, голос, daily note."""
        if self.root.state() == "withdrawn":
            self.root.deiconify()
            self.root.lift()
            self.root.attributes("-topmost", True)

        from autostart import is_autostart_enabled, set_autostart

        dialog = ctk.CTkToplevel(self.root)
        dialog.title("Настройки CtrlNote")
        dialog.geometry("500x620")
        dialog.minsize(460, 520)
        dialog.attributes("-topmost", True)
        dialog.transient(self.root)
        dialog.focus_force()
        dialog.lift()
        dialog.grab_set()
        dialog.update_idletasks()
        from ui_icon import apply_window_icon

        apply_window_icon(dialog)
        try:
            x = self.root.winfo_rootx() + 20
            y = self.root.winfo_rooty() + 20
            dialog.geometry(f"+{x}+{y}")
        except tk.TclError:
            pass

        config = load_config()
        scroll = ctk.CTkScrollableFrame(dialog, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=8, pady=(8, 0))
        body = scroll

        ctk.CTkLabel(body, text="Vault Obsidian").pack(anchor="w", padx=8)
        vault_row = ctk.CTkFrame(body, fg_color="transparent")
        vault_row.pack(fill="x", padx=8, pady=(4, 12))
        vault_var = ctk.StringVar(value=config.get("vault_path", ""))
        ctk.CTkEntry(vault_row, textvariable=vault_var).pack(
            side="left", fill="x", expand=True, padx=(0, 8)
        )

        def browse() -> None:
            from tkinter import filedialog

            path = filedialog.askdirectory(title="Выберите vault", parent=dialog)
            if path:
                vault_var.set(path)

        ctk.CTkButton(vault_row, text="Обзор", width=80, command=browse).pack(side="right")

        ctk.CTkLabel(body, text="Горячая клавиша").pack(anchor="w", padx=8)
        hotkey_var = ctk.StringVar(value=config.get("hotkey", "ctrl+alt+n"))
        ctk.CTkEntry(body, textvariable=hotkey_var).pack(fill="x", padx=8, pady=(4, 12))

        autostart_var = ctk.BooleanVar(value=is_autostart_enabled())
        ctk.CTkCheckBox(
            body,
            text="Запускать вместе с Windows",
            variable=autostart_var,
        ).pack(anchor="w", padx=8, pady=(0, 8))

        auto_folder_var = ctk.BooleanVar(value=bool(config.get("auto_folder", True)))
        ctk.CTkCheckBox(
            body,
            text="Автовыбор папки по активному окну",
            variable=auto_folder_var,
        ).pack(anchor="w", padx=8, pady=(0, 12))

        ctk.CTkLabel(body, text="Голос").pack(anchor="w", padx=8)
        engine_var = ctk.StringVar(value=str(config.get("voice_engine", "local")))
        ctk.CTkOptionMenu(
            body,
            variable=engine_var,
            values=["local", "openai"],
            width=160,
        ).pack(anchor="w", padx=8, pady=(4, 8))

        ctk.CTkLabel(body, text="Модель Whisper (local)").pack(anchor="w", padx=8)
        model_var = ctk.StringVar(value=str(config.get("whisper_model", "small")))
        ctk.CTkOptionMenu(
            body,
            variable=model_var,
            values=["tiny", "base", "small", "medium"],
            width=160,
        ).pack(anchor="w", padx=8, pady=(4, 8))

        ctk.CTkLabel(body, text="OpenAI API key (для openai)").pack(anchor="w", padx=8)
        api_var = ctk.StringVar(value=str(config.get("openai_api_key", "")))
        ctk.CTkEntry(body, textvariable=api_var, show="*").pack(fill="x", padx=8, pady=(4, 8))

        lang_row = ctk.CTkFrame(body, fg_color="transparent")
        lang_row.pack(fill="x", padx=8, pady=(0, 8))
        ctk.CTkLabel(lang_row, text="Язык").pack(side="left", padx=(0, 8))
        lang_var = ctk.StringVar(value=str(config.get("voice_language", "ru")))
        ctk.CTkEntry(lang_row, textvariable=lang_var, width=80).pack(side="left")

        save_audio_var = ctk.BooleanVar(value=bool(config.get("save_voice_audio", False)))
        ctk.CTkCheckBox(
            body,
            text="Сохранять аудио в recordings",
            variable=save_audio_var,
        ).pack(anchor="w", padx=8, pady=(0, 12))

        ctk.CTkLabel(body, text="Daily note").pack(anchor="w", padx=8)
        link_daily_var = ctk.BooleanVar(value=bool(config.get("link_daily_note", False)))
        ctk.CTkCheckBox(
            body,
            text="Добавлять [[сегодня]] в конец заметки",
            variable=link_daily_var,
        ).pack(anchor="w", padx=8, pady=(4, 4))

        append_daily_var = ctk.BooleanVar(value=bool(config.get("append_daily_note", False)))
        ctk.CTkCheckBox(
            body,
            text="Писать ссылку в файл дня Obsidian",
            variable=append_daily_var,
        ).pack(anchor="w", padx=8, pady=(0, 8))

        ctk.CTkLabel(body, text="Папка daily-note (пусто = корень)").pack(anchor="w", padx=8)
        daily_folder_var = ctk.StringVar(value=str(config.get("daily_note_folder", "")))
        ctk.CTkEntry(body, textvariable=daily_folder_var).pack(fill="x", padx=8, pady=(4, 8))

        ctk.CTkLabel(body, text="Формат имени дня").pack(anchor="w", padx=8)
        daily_fmt_var = ctk.StringVar(value=str(config.get("daily_note_format", "YYYY-MM-DD")))
        ctk.CTkOptionMenu(
            body,
            variable=daily_fmt_var,
            values=["YYYY-MM-DD", "DD-MM-YYYY", "YYYYMMDD"],
            width=160,
        ).pack(anchor="w", padx=8, pady=(4, 12))

        footer = ctk.CTkFrame(dialog, fg_color="transparent")
        footer.pack(fill="x", padx=16, pady=16)

        def save_settings() -> None:
            """Записывает настройки на диск и применяет хоткей/автозапуск."""
            old_hotkey = str(config.get("hotkey", "ctrl+alt+n"))
            new_hotkey = hotkey_var.get().strip().lower() or "ctrl+alt+n"
            config["vault_path"] = vault_var.get().strip()
            config["hotkey"] = new_hotkey
            config["whisper_model"] = model_var.get().strip() or "small"
            config["voice_language"] = lang_var.get().strip() or "ru"
            config["voice_engine"] = engine_var.get().strip() or "local"
            config["openai_api_key"] = api_var.get().strip()
            config["save_voice_audio"] = bool(save_audio_var.get())
            config["auto_folder"] = bool(auto_folder_var.get())
            config["link_daily_note"] = bool(link_daily_var.get())
            config["append_daily_note"] = bool(append_daily_var.get())
            config["daily_note_folder"] = daily_folder_var.get().strip()
            config["daily_note_format"] = daily_fmt_var.get().strip() or "YYYY-MM-DD"
            want_autostart = bool(autostart_var.get())
            try:
                set_autostart(want_autostart)
            except OSError as exc:
                messagebox.showerror(
                    "CtrlNote",
                    f"Не удалось изменить автозапуск:\n{exc}",
                    parent=dialog,
                )
                return
            config["autostart"] = want_autostart
            try:
                save_config(config)
            except Exception as exc:  # noqa: BLE001 — SecretStorageError / IO
                from config import SecretStorageError

                if isinstance(exc, SecretStorageError):
                    messagebox.showerror(
                        "CtrlNote",
                        f"Не удалось безопасно сохранить API-ключ:\n{exc}",
                        parent=dialog,
                    )
                    return
                messagebox.showerror(
                    "CtrlNote",
                    f"Не удалось сохранить настройки:\n{exc}",
                    parent=dialog,
                )
                return
            if new_hotkey != old_hotkey and self.on_hotkey_changed:
                try:
                    self.on_hotkey_changed()
                except Exception as exc:  # noqa: BLE001
                    messagebox.showerror(
                        "CtrlNote",
                        f"Не удалось применить горячую клавишу:\n{exc}",
                        parent=dialog,
                    )
                    return
            dialog.destroy()
            if self._visible:
                self._refresh_folders()

        ctk.CTkButton(footer, text="Сохранить", width=120, command=save_settings).pack(
            side="right"
        )
        ctk.CTkButton(footer, text="Отмена", width=90, command=dialog.destroy).pack(
            side="right", padx=(0, 8)
        )

    def run(self) -> None:
        """Запускает цикл обработки событий окна (пока программа открыта)."""
        self.root.mainloop()

    def quit(self) -> None:
        """Закрывает окно и завершает цикл интерфейса."""
        try:
            self.root.quit()
            self.root.destroy()
        except tk.TclError:
            pass

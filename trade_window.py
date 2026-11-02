"""
Окно журнала трейдера (Ctrl+Alt+T).

Шаг 1 — большие кнопки «профит / убыток / в ноль».
Шаг 2 — параметры сделки: монета, вход/выход в SOL, капа, сетап, эмоции, ошибки, скрины.
Списки чипов редактируются прямо в окне: «+ своё» добавляет, правый клик — убирает.
"""

from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont
from datetime import datetime
from pathlib import Path
from tkinter import filedialog
from typing import Callable
from urllib.parse import quote

import customtkinter as ctk
from PIL import Image

import trade_journal as tj
from config import load_config, save_config
from i18n import get_language, t

# Палитра «биржевого терминала»
BG = "#0b0e11"
PANEL = "#12161c"
FIELD = "#181d24"
BORDER = "#262c35"
TEXT = "#eaecef"
MUTED = "#848e9c"
GREEN = "#0ecb81"
GREEN_DIM = "#0d2a20"
RED = "#f6465d"
RED_DIM = "#331820"
YELLOW = "#f0b90b"
YELLOW_DIM = "#2e260c"
BLUE = "#5b8def"
BLUE_DIM = "#18233a"

MONO = "Consolas"
WRAP_WIDTH = 560

RESULT_COLORS = {
    tj.RESULT_PROFIT: (GREEN, GREEN_DIM),
    tj.RESULT_LOSS: (RED, RED_DIM),
    tj.RESULT_BE: (YELLOW, YELLOW_DIM),
}

# Виртуальные коды клавиш: Ctrl+V/C/X/A работают и в русской раскладке
_VK_A, _VK_C, _VK_V, _VK_X = 65, 67, 86, 88


def _trade_vault(config: dict) -> str:
    return str(config.get("trade_vault_path") or config.get("vault_path") or "")


class ChipGroup:
    """Строка «чипов»: одиночный или множественный выбор + «+ своё» и удаление правым кликом."""

    def __init__(
        self,
        parent: ctk.CTkFrame,
        group: str,
        items: list[str],
        multi: bool,
        accent: tuple[str, str],
        on_change: Callable[[], None] | None = None,
    ) -> None:
        self.group = group
        self.items = list(items)
        self.multi = multi
        self.color, self.dim = accent
        self.on_change = on_change
        self.selected: list[str] = []
        self.frame = ctk.CTkFrame(parent, fg_color="transparent")
        self._font = ctk.CTkFont(size=12)
        self._measure = tkfont.Font(family="Segoe UI", size=10)
        self._adding = False
        self.render()

    def get(self) -> list[str]:
        return [item for item in self.items if item in self.selected]

    def set(self, values: list[str]) -> None:
        self.selected = [v for v in values if v in self.items]
        self.render()

    def _toggle(self, item: str) -> None:
        if item in self.selected:
            self.selected.remove(item)
        elif self.multi:
            self.selected.append(item)
        else:
            self.selected = [item]
        self.render()
        if self.on_change:
            self.on_change()

    def _remove(self, item: str) -> None:
        options = tj.remove_option(self.group, item, get_language())
        self.items = options[self.group]
        if item in self.selected:
            self.selected.remove(item)
        self.render()

    def _add(self, value: str) -> None:
        if not self._adding:  # Enter и потеря фокуса приходят оба — второй игнорируем
            return
        value = value.strip()
        self._adding = False
        if value:
            options = tj.add_option(self.group, value, get_language())
            self.items = options[self.group]
            if value not in self.selected:
                if not self.multi:
                    self.selected = []
                self.selected.append(value)
        self.render()

    def _context_menu(self, event: tk.Event, item: str) -> None:
        menu = tk.Menu(self.frame, tearoff=0, bg=PANEL, fg=TEXT, activebackground=RED_DIM)
        menu.add_command(label=t("trade_remove", name=item), command=lambda: self._remove(item))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def render(self) -> None:
        for child in self.frame.winfo_children():
            child.destroy()

        row = ctk.CTkFrame(self.frame, fg_color="transparent")
        row.pack(fill="x", anchor="w")
        used = 0

        def place(widget_width: int) -> ctk.CTkFrame:
            nonlocal row, used
            if used and used + widget_width > WRAP_WIDTH:
                row = ctk.CTkFrame(self.frame, fg_color="transparent")
                row.pack(fill="x", anchor="w", pady=(4, 0))
                used = 0
            used += widget_width + 6
            return row

        for item in self.items:
            on = item in self.selected
            width = self._measure.measure(item) + 26
            btn = ctk.CTkButton(
                place(width),
                text=item,
                width=width,
                height=26,
                corner_radius=13,
                font=self._font,
                fg_color=self.dim if on else FIELD,
                hover_color=self.dim,
                border_width=1,
                border_color=self.color if on else BORDER,
                text_color=self.color if on else TEXT,
                command=lambda i=item: self._toggle(i),
            )
            btn.pack(side="left", padx=(0, 6))
            btn.bind("<Button-3>", lambda e, i=item: self._context_menu(e, i))
            label = getattr(btn, "_text_label", None)
            if label is not None:
                label.bind("<Button-3>", lambda e, i=item: self._context_menu(e, i))

        if self._adding:
            entry = ctk.CTkEntry(
                place(130), width=130, height=26, corner_radius=13, fg_color=FIELD, border_color=self.color
            )
            entry.pack(side="left")
            entry.bind("<Return>", lambda _e: self._add(entry.get()))
            entry.bind("<Escape>", lambda _e: (self._cancel_add(), "break")[1])
            entry.bind("<FocusOut>", lambda _e: self._add(entry.get()))
            entry.after(10, entry.focus_set)
        else:
            label = t("trade_add")
            width = self._measure.measure(label) + 26
            ctk.CTkButton(
                place(width),
                text=label,
                width=width,
                height=26,
                corner_radius=13,
                font=self._font,
                fg_color="transparent",
                hover_color=FIELD,
                border_width=1,
                border_color=BORDER,
                text_color=MUTED,
                command=self._start_add,
            ).pack(side="left")

    def _start_add(self) -> None:
        self._adding = True
        self.render()

    def _cancel_add(self) -> None:
        self._adding = False
        self.render()


class TradeWindow:
    """Всплывающее окно сделки поверх всех окон."""

    def __init__(self, master: ctk.CTk, on_saved: Callable[[str], None] | None = None) -> None:
        self.master = master
        self.on_saved = on_saved
        self.lang = get_language()
        self.win = ctk.CTkToplevel(master)
        self.win.withdraw()
        self.win.title("CtrlNote · Trade")
        self.win.configure(fg_color=BG)
        self.win.attributes("-topmost", True)
        self.win.protocol("WM_DELETE_WINDOW", self.hide)
        height = min(880, self.win.winfo_screenheight() - 80)
        self.win.geometry(f"640x{height}")
        self.win.minsize(600, 520)

        self.result: str | None = None
        self.rating = 0
        self._visible = False
        self._images: list[tuple[str, Image.Image]] = []
        self._price_result: float | None = None
        self._price_user_edited = False

        self.vars = {
            name: ctk.StringVar()
            for name in ("coin", "ca", "entry", "exit", "sol_usd", "mcap_in", "mcap_out", "stop")
        }
        self.status_var = ctk.StringVar()

        self._build()
        self.win.bind("<Escape>", lambda _e: self.hide())
        self.win.bind("<Control-Return>", lambda _e: self._save())
        self.win.bind("<Control-KP_Enter>", lambda _e: self._save())
        self.win.bind("<Key>", self._on_key)
        self.win.bind("<Control-KeyPress>", self._on_ctrl_key)
        for name in ("entry", "exit", "sol_usd", "mcap_in", "mcap_out"):
            self.vars[name].trace_add("write", lambda *_: self._update_pnl())

    # ------------------------------------------------------------ layout

    def _label(self, parent, text: str) -> ctk.CTkLabel:  # noqa: ANN001
        return ctk.CTkLabel(
            parent, text=text.upper(), text_color=MUTED, font=ctk.CTkFont(size=11, weight="bold"), anchor="w"
        )

    def _entry(self, parent, var: ctk.StringVar, mono: bool = False, placeholder: str = "") -> ctk.CTkEntry:  # noqa: ANN001
        return ctk.CTkEntry(
            parent,
            textvariable=var,
            height=32,
            fg_color=FIELD,
            border_color=BORDER,
            border_width=1,
            text_color=TEXT,
            placeholder_text=placeholder,
            font=ctk.CTkFont(family=MONO, size=14) if mono else ctk.CTkFont(size=13),
        )

    def _textbox(self, parent, height: int) -> ctk.CTkTextbox:  # noqa: ANN001
        box = ctk.CTkTextbox(
            parent, height=height, wrap="word", fg_color=FIELD, border_color=BORDER, border_width=1,
            text_color=TEXT, font=ctk.CTkFont(size=13),
        )
        return box

    def _build(self) -> None:
        # Цветная полоска сверху — меняет цвет по результату сделки
        self.accent_bar = ctk.CTkFrame(self.win, height=3, corner_radius=0, fg_color=YELLOW)
        self.accent_bar.pack(fill="x")

        header = ctk.CTkFrame(self.win, fg_color=PANEL, corner_radius=0, height=46)
        header.pack(fill="x")
        self.header = header
        ctk.CTkLabel(
            header, text="◢ CTRLNOTE", text_color=YELLOW, font=ctk.CTkFont(family=MONO, size=14, weight="bold")
        ).pack(side="left", padx=(16, 4), pady=10)
        ctk.CTkLabel(
            header, text="TRADE", text_color=MUTED, font=ctk.CTkFont(family=MONO, size=14)
        ).pack(side="left")

        icon = {"width": 34, "height": 28, "fg_color": "transparent", "hover_color": FIELD, "text_color": MUTED}
        ctk.CTkButton(header, text="⚙", command=self.open_settings, **icon).pack(side="right", padx=(0, 10))
        ctk.CTkButton(
            header, text=t("trade_journal"), command=self.open_journal, width=90, height=28,
            fg_color="transparent", hover_color=FIELD, text_color=MUTED,
        ).pack(side="right")
        self.stats_label = ctk.CTkLabel(header, text="", font=ctk.CTkFont(family=MONO, size=12), text_color=MUTED)
        self.stats_label.pack(side="right", padx=10)

        self.tilt_label = ctk.CTkLabel(
            self.win, text="", fg_color=RED_DIM, text_color=RED, height=30,
            font=ctk.CTkFont(size=12, weight="bold"),
        )

        self.body = ctk.CTkFrame(self.win, fg_color="transparent")
        self.body.pack(fill="both", expand=True)
        self._build_step1()
        self._build_step2()

    def _build_step1(self) -> None:
        self.step1 = ctk.CTkFrame(self.body, fg_color="transparent")
        ctk.CTkLabel(
            self.step1, text=t("trade_question"), text_color=TEXT, font=ctk.CTkFont(size=22, weight="bold")
        ).pack(pady=(70, 28))

        row = ctk.CTkFrame(self.step1, fg_color="transparent")
        row.pack()
        big = {"width": 230, "height": 150, "corner_radius": 14, "border_width": 2,
               "font": ctk.CTkFont(family=MONO, size=24, weight="bold")}
        ctk.CTkButton(
            row, text=f"▲\n{t('trade_profit')}", fg_color=GREEN_DIM, hover_color="#124232",
            border_color=GREEN, text_color=GREEN, command=lambda: self.choose_result(tj.RESULT_PROFIT), **big,
        ).pack(side="left", padx=10)
        ctk.CTkButton(
            row, text=f"▼\n{t('trade_loss')}", fg_color=RED_DIM, hover_color="#4a1f2a",
            border_color=RED, text_color=RED, command=lambda: self.choose_result(tj.RESULT_LOSS), **big,
        ).pack(side="left", padx=10)
        ctk.CTkButton(
            self.step1, text=f"◆  {t('trade_be')}", width=200, height=44, corner_radius=10, border_width=1,
            fg_color=FIELD, hover_color=YELLOW_DIM, border_color=BORDER, text_color=YELLOW,
            font=ctk.CTkFont(family=MONO, size=15, weight="bold"),
            command=lambda: self.choose_result(tj.RESULT_BE),
        ).pack(pady=(20, 0))
        ctk.CTkLabel(
            self.step1, text=t("trade_step_hint"), text_color=MUTED, font=ctk.CTkFont(family=MONO, size=12)
        ).pack(pady=(26, 0))

    def _build_step2(self) -> None:
        self.step2 = ctk.CTkFrame(self.body, fg_color="transparent")

        # Переключатель результата (можно поменять после выбора)
        strip = ctk.CTkFrame(self.step2, fg_color="transparent")
        strip.pack(fill="x", padx=18, pady=(12, 6))
        self.result_buttons: dict[str, ctk.CTkButton] = {}
        for result, text in (
            (tj.RESULT_PROFIT, f"▲ {t('trade_profit')}"),
            (tj.RESULT_LOSS, f"▼ {t('trade_loss')}"),
            (tj.RESULT_BE, f"◆ {t('trade_be')}"),
        ):
            btn = ctk.CTkButton(
                strip, text=text, height=34, corner_radius=8, border_width=1,
                font=ctk.CTkFont(family=MONO, size=13, weight="bold"),
                command=lambda r=result: self.choose_result(r),
            )
            btn.pack(side="left", expand=True, fill="x", padx=(0, 6))
            self.result_buttons[result] = btn

        form = ctk.CTkScrollableFrame(
            self.step2, fg_color="transparent", scrollbar_button_color=BORDER,
            scrollbar_button_hover_color=MUTED,
        )
        form.pack(fill="both", expand=True, padx=8)
        self.form = form

        def grid_row(*fields: tuple[str, str, bool, str]) -> list[ctk.CTkEntry]:
            frame = ctk.CTkFrame(form, fg_color="transparent")
            frame.pack(fill="x", padx=10, pady=(6, 0))
            entries = []
            for col, (label, var, mono, ph) in enumerate(fields):
                frame.grid_columnconfigure(col, weight=1, uniform="f")
                self._label(frame, label).grid(row=0, column=col, sticky="w", padx=(0 if col == 0 else 8, 0))
                entry = self._entry(frame, self.vars[var], mono=mono, placeholder=ph)
                entry.grid(row=1, column=col, sticky="ew", padx=(0 if col == 0 else 8, 0))
                entries.append(entry)
            return entries

        self.coin_entry, = grid_row((t("trade_coin"), "coin", False, "$WIF"))[:1]
        grid_row((t("trade_ca"), "ca", True, ""))
        _, _, self.price_entry = grid_row(
            (t("trade_entry"), "entry", True, "0.5"),
            (t("trade_exit"), "exit", True, "0.583"),
            (t("trade_sol_usd"), "sol_usd", True, "…"),
        )
        self.price_entry.bind("<KeyRelease>", lambda _e: setattr(self, "_price_user_edited", True))
        grid_row(
            (t("trade_mcap_in"), "mcap_in", True, "120K"),
            (t("trade_mcap_out"), "mcap_out", True, "450K"),
            (t("trade_stop"), "stop", True, "-30%"),
        )

        options = tj.load_options(get_language())

        def chips(title: str, group: str, multi: bool, accent: tuple[str, str]) -> ChipGroup:
            self._label(form, title).pack(fill="x", padx=10, pady=(12, 4))
            chip = ChipGroup(form, group, options[group], multi, accent)
            chip.frame.pack(fill="x", padx=10)
            return chip

        def textbox(title: str, height: int) -> ctk.CTkTextbox:
            self._label(form, title).pack(fill="x", padx=10, pady=(12, 4))
            box = self._textbox(form, height)
            box.pack(fill="x", padx=10)
            return box

        self.platform_chips = chips(t("trade_platform"), "platforms", False, (YELLOW, YELLOW_DIM))
        self.risk_chips = chips(t("trade_risk"), "risk", False, (YELLOW, YELLOW_DIM))
        self.setup_chips = chips(t("trade_setup"), "setups", True, (BLUE, BLUE_DIM))
        self.why_in = textbox(t("trade_why_in"), 64)
        self.why_out = textbox(t("trade_why_out"), 64)
        self.emotion_chips = chips(t("trade_emotions"), "emotions", True, (BLUE, BLUE_DIM))
        self.mistake_chips = chips(t("trade_mistakes"), "mistakes", True, (RED, RED_DIM))

        self._label(form, t("trade_rating")).pack(fill="x", padx=10, pady=(12, 2))
        stars = ctk.CTkFrame(form, fg_color="transparent")
        stars.pack(fill="x", padx=6)
        self.star_buttons = []
        for value in range(1, 6):
            btn = ctk.CTkButton(
                stars, text="★", width=36, height=34, fg_color="transparent", hover_color=FIELD,
                font=ctk.CTkFont(size=24), command=lambda v=value: self._set_rating(v),
            )
            btn.pack(side="left")
            self.star_buttons.append(btn)

        notes_head = ctk.CTkFrame(form, fg_color="transparent")
        notes_head.pack(fill="x", padx=10, pady=(12, 4))
        self._label(notes_head, t("trade_notes")).pack(side="left")
        ctk.CTkButton(
            notes_head, text=t("trade_paste_shot"), width=130, height=24, fg_color=FIELD,
            hover_color=BORDER, text_color=TEXT, command=self._paste_into_notes,
        ).pack(side="right")
        self.notes = self._textbox(form, 110)
        self.notes.pack(fill="x", padx=10, pady=(0, 16))
        inner = getattr(self.notes, "_textbox", None)
        for widget in filter(None, (self.notes, inner)):
            for seq in ("<Control-v>", "<Control-V>", "<Shift-Insert>"):
                widget.bind(seq, lambda _e: (self._paste_into_notes(), "break")[1])

        # Подвал: живой PnL + кнопки
        footer = ctk.CTkFrame(self.step2, fg_color=PANEL, corner_radius=0)
        footer.pack(fill="x", side="bottom")
        left = ctk.CTkFrame(footer, fg_color="transparent")
        left.pack(side="left", padx=16, pady=10)
        self.pnl_label = ctk.CTkLabel(
            left, text="—", font=ctk.CTkFont(family=MONO, size=22, weight="bold"), text_color=MUTED, anchor="w"
        )
        self.pnl_label.pack(anchor="w")
        self.pnl_sub = ctk.CTkLabel(
            left, text="", font=ctk.CTkFont(family=MONO, size=12), text_color=MUTED, anchor="w"
        )
        self.pnl_sub.pack(anchor="w")

        self.save_btn = ctk.CTkButton(
            footer, text=t("trade_save"), width=170, height=40, corner_radius=8,
            font=ctk.CTkFont(size=14, weight="bold"), command=self._save,
        )
        self.save_btn.pack(side="right", padx=(6, 16), pady=10)
        ctk.CTkButton(
            footer, text=t("trade_reset"), width=90, height=40, fg_color="transparent",
            hover_color=FIELD, text_color=MUTED, command=self.reset,
        ).pack(side="right")

        ctk.CTkLabel(
            self.step2, textvariable=self.status_var, text_color=YELLOW, font=ctk.CTkFont(size=12), anchor="w"
        ).pack(fill="x", side="bottom", padx=18, pady=(2, 0))

    # ------------------------------------------------------------ state

    def choose_result(self, result: str) -> None:
        self.result = result
        color, dim = RESULT_COLORS[result]
        self.accent_bar.configure(fg_color=color)
        for key, btn in self.result_buttons.items():
            c, d = RESULT_COLORS[key]
            on = key == result
            btn.configure(
                fg_color=d if on else FIELD, border_color=c if on else BORDER,
                text_color=c if on else MUTED, hover_color=d,
            )
        self.save_btn.configure(fg_color=color, hover_color=color, text_color=BG)
        if self.step2.winfo_manager() == "":
            self.step1.pack_forget()
            self.step2.pack(fill="both", expand=True)
            self.win.after(30, self.coin_entry.focus_set)
        self._update_pnl()

    def _set_rating(self, value: int) -> None:
        self.rating = 0 if value == self.rating else value
        for index, btn in enumerate(self.star_buttons, start=1):
            btn.configure(text_color=YELLOW if index <= self.rating else BORDER)

    def _current_trade(self) -> tj.Trade:
        coin = self.vars["coin"].get().strip().lstrip("$")
        ca = self.vars["ca"].get().strip()
        if not coin and ca:
            coin = f"{ca[:4]}…{ca[-4:]}"
        platform = self.platform_chips.get()
        risk = self.risk_chips.get()
        return tj.Trade(
            result=self.result or tj.RESULT_BE,
            coin=coin,
            ca=ca,
            platform=platform[0] if platform else "",
            when=datetime.now(),
            entry_sol=tj.parse_number(self.vars["entry"].get()),
            exit_sol=tj.parse_number(self.vars["exit"].get()),
            sol_usd=tj.parse_number(self.vars["sol_usd"].get()),
            mcap_entry=self.vars["mcap_in"].get().strip(),
            mcap_exit=self.vars["mcap_out"].get().strip(),
            stop=self.vars["stop"].get().strip(),
            risk=risk[0] if risk else "",
            setups=self.setup_chips.get(),
            emotions=self.emotion_chips.get(),
            mistakes=self.mistake_chips.get(),
            rating=self.rating,
            why_in=self.why_in.get("1.0", "end").strip(),
            why_out=self.why_out.get("1.0", "end").strip(),
            notes=self.notes.get("1.0", "end").strip(),
        )

    def _update_pnl(self) -> None:
        trade = self._current_trade()
        pnl = trade.pnl_sol
        if pnl is None:
            self.pnl_label.configure(text="— SOL", text_color=MUTED)
            sub = f"x{trade.mcap_multiple:g} mcap" if trade.mcap_multiple else ""
            self.pnl_sub.configure(text=sub, text_color=MUTED)
            return
        color = GREEN if pnl > 0 else RED if pnl < 0 else YELLOW
        self.pnl_label.configure(text=f"{tj.fmt_signed(pnl)} SOL", text_color=color)
        parts = []
        if trade.pnl_usd is not None:
            parts.append(("+" if trade.pnl_usd > 0 else "-" if trade.pnl_usd < 0 else "") + f"${abs(trade.pnl_usd):.2f}")
        if trade.pnl_pct is not None:
            parts.append(f"{tj.fmt_signed(trade.pnl_pct, 1)}%")
        if trade.mcap_multiple:
            parts.append(f"x{trade.mcap_multiple:g} mcap")
        warn = ""
        if self.result == tj.RESULT_PROFIT and pnl < 0:
            warn = "   ⚠ " + t("trade_mismatch_profit")
        elif self.result == tj.RESULT_LOSS and pnl > 0:
            warn = "   ⚠ " + t("trade_mismatch_loss")
        self.pnl_sub.configure(text=" · ".join(parts) + warn, text_color=YELLOW if warn else color)

    def _refresh_stats(self) -> None:
        config = load_config()
        vault = _trade_vault(config)
        records = tj.load_trades(vault, tj.trade_folder(config, self.lang)) if vault else []
        today = tj.today_records(records)
        if today:
            stats = tj.compute_stats(today)
            wr = f"WR {stats.winrate}%" if stats.winrate is not None else ""
            text = f"{t('trade_today')}  {tj.fmt_signed(stats.pnl_sol)} SOL · {stats.trades} · {wr}".rstrip(" ·")
            color = GREEN if stats.pnl_sol > 0 else RED if stats.pnl_sol < 0 else MUTED
        else:
            text, color = t("trade_no_trades"), MUTED
        self.stats_label.configure(text=text, text_color=color)

        streak = tj.loss_streak(today)
        if streak >= 3:
            self.tilt_label.configure(text=t("trade_tilt", n=streak))
            self.tilt_label.pack(fill="x", after=self.header)
        else:
            self.tilt_label.pack_forget()

    def reset(self) -> None:
        self.result = None
        for var in self.vars.values():
            var.set("")
        for box in (self.why_in, self.why_out, self.notes):
            box.delete("1.0", "end")
        for chip in (self.risk_chips, self.setup_chips, self.emotion_chips, self.mistake_chips):
            chip.set([])
        config = load_config()
        last_platform = str(config.get("trade_platform") or "")
        self.platform_chips.set([last_platform] if last_platform else [])
        cached = tj.parse_number(config.get("trade_sol_usd"))
        if cached:
            self.vars["sol_usd"].set(f"{cached:g}")
        self._price_user_edited = False
        self._set_rating(0)
        self.rating = 0
        self._images.clear()
        self.status_var.set("")
        self.accent_bar.configure(fg_color=YELLOW)
        self.step2.pack_forget()
        self.step1.pack(fill="both", expand=True)
        self.form._parent_canvas.yview_moveto(0)  # noqa: SLF001

    # ------------------------------------------------------------ show / hide

    def show(self) -> None:
        fresh = self.result is None
        if fresh:
            self.reset()
            self._prefill_ca_from_clipboard()
        self._refresh_stats()
        self._fetch_price()
        self.win.deiconify()
        self.win.lift()
        self.win.attributes("-topmost", True)
        self._center()
        self.win.focus_force()
        self._visible = True
        if not fresh:
            self.win.after(30, self.coin_entry.focus_set)

    def hide(self) -> None:
        # Черновик не теряем: Esc просто прячет окно, сброс — кнопкой или после записи
        self.win.withdraw()
        self._visible = False

    def toggle(self) -> None:
        if self._visible and self.win.state() == "normal":
            self.hide()
        else:
            self.show()

    def _center(self) -> None:
        self.win.update_idletasks()
        w, h = self.win.winfo_width(), self.win.winfo_height()
        x = max(0, (self.win.winfo_screenwidth() - w) // 2)
        y = max(0, (self.win.winfo_screenheight() - h) // 2 - 20)
        self.win.geometry(f"+{x}+{y}")

    def _prefill_ca_from_clipboard(self) -> None:
        try:
            text = self.win.clipboard_get().strip()
        except tk.TclError:
            return
        if tj.looks_like_ca(text):
            self.vars["ca"].set(text)

    def _fetch_price(self) -> None:
        self._price_result = None
        tj.fetch_sol_usd_async(lambda price: setattr(self, "_price_result", price))
        self._poll_price(25)

    def _poll_price(self, tries: int) -> None:
        # Ответ из фонового потока забираем в главном потоке Tk
        price = self._price_result
        if price:
            if not self._price_user_edited:
                self.vars["sol_usd"].set(f"{price:g}")
            config = load_config()
            config["trade_sol_usd"] = price
            save_config(config)
            return
        if tries > 0:
            self.win.after(300, lambda: self._poll_price(tries - 1))

    # ------------------------------------------------------------ keys & paste

    def _on_key(self, event: tk.Event) -> None:
        if self.result is None and event.char in {"1", "2", "3"}:
            self.choose_result({"1": tj.RESULT_PROFIT, "2": tj.RESULT_LOSS, "3": tj.RESULT_BE}[event.char])

    def _on_ctrl_key(self, event: tk.Event) -> str | None:
        """Ctrl+V/C/X/A в русской раскладке (в английской Tk справляется сам)."""
        if event.keysym.lower() in {"v", "c", "x", "a"} or event.keycode not in {_VK_A, _VK_C, _VK_V, _VK_X}:
            return None
        widget = self.win.focus_get()
        if widget is None:
            return None
        if event.keycode == _VK_V:
            notes_inner = getattr(self.notes, "_textbox", None)
            if widget in (self.notes, notes_inner):
                self._paste_into_notes()
            else:
                widget.event_generate("<<Paste>>")
        elif event.keycode == _VK_C:
            widget.event_generate("<<Copy>>")
        elif event.keycode == _VK_X:
            widget.event_generate("<<Cut>>")
        elif event.keycode == _VK_A:
            try:
                widget.select_range(0, "end")
            except (AttributeError, tk.TclError):
                widget.event_generate("<<SelectAll>>")
        return "break"

    def _paste_into_notes(self) -> None:
        from PIL import ImageGrab

        clipped = ImageGrab.grabclipboard()
        image: Image.Image | None = None
        if isinstance(clipped, Image.Image):
            image = clipped.copy()
        elif isinstance(clipped, list):
            for item in clipped:
                path = Path(str(item))
                if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"} and path.is_file():
                    with Image.open(path) as img:
                        image = img.copy()
                    break
        if image is not None:
            coin = tj.sanitize_filename(self.vars["coin"].get().strip().lstrip("$"), 30) or "trade"
            name = f"Trade {coin} {datetime.now():%Y%m%d%H%M%S}-{len(self._images) + 1}.png"
            self._images.append((name, image))
            self.notes.insert("insert", f"![[{name}]]\n")
            self.notes.focus_set()
            return
        try:
            text = self.win.clipboard_get()
        except tk.TclError:
            return
        self.notes.insert("insert", text)

    # ------------------------------------------------------------ save

    def _save(self) -> None:
        if self.result is None:
            return
        trade = self._current_trade()
        if not trade.coin:
            self.status_var.set(t("trade_need_coin"))
            self.coin_entry.focus_set()
            return

        config = load_config()
        vault = _trade_vault(config)
        if not vault or not Path(vault).expanduser().is_dir():
            self.status_var.set(t("trade_no_vault"))
            self.open_settings()
            return
        try:
            path = tj.save_trade(
                trade,
                vault,
                folder=tj.trade_folder(config, self.lang),
                attachments_folder=tj.attachments_folder(config, self.lang),
                attachments=list(self._images),
                lang=get_language(),
            )
        except (OSError, ValueError) as exc:
            self.status_var.set(t("save_error", exc=exc))
            return

        config["trade_platform"] = trade.platform
        save_config(config)
        if self.on_saved:
            self.on_saved(str(path))
        self.result = None
        self.hide()

    # ------------------------------------------------------------ journal & settings

    def open_journal(self) -> None:
        import os

        config = load_config()
        vault = _trade_vault(config)
        if not vault:
            return
        path = Path(vault).expanduser().resolve() / tj.dashboard_name(self.lang)
        if not path.exists():
            try:
                tj.write_dashboard(vault, tj.trade_folder(config, self.lang), self.lang)
            except OSError:
                return
        try:
            os.startfile(f"obsidian://open?path={quote(str(path))}")  # noqa: S606
        except OSError:
            os.startfile(str(path))  # noqa: S606

    def open_settings(self) -> None:
        config = load_config()
        dialog = ctk.CTkToplevel(self.win)
        dialog.title(t("trade_settings_title"))
        dialog.configure(fg_color=BG)
        dialog.geometry("520x380")
        dialog.attributes("-topmost", True)
        dialog.transient(self.win)

        body = ctk.CTkFrame(dialog, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=18, pady=14)

        vault_var = ctk.StringVar(value=str(config.get("trade_vault_path") or ""))
        folder_var = ctk.StringVar(value=tj.trade_folder(config, self.lang))
        att_var = ctk.StringVar(value=tj.attachments_folder(config, self.lang))
        hotkey_var = ctk.StringVar(value=str(config.get("trade_hotkey") or "ctrl+alt+t"))

        self._label(body, t("trade_vault")).pack(fill="x", pady=(0, 4))
        row = ctk.CTkFrame(body, fg_color="transparent")
        row.pack(fill="x")
        self._entry(row, vault_var).pack(side="left", fill="x", expand=True)

        def browse() -> None:
            chosen = filedialog.askdirectory(parent=dialog, initialdir=vault_var.get() or None)
            if chosen:
                vault_var.set(chosen)

        ctk.CTkButton(row, text=t("browse"), width=80, command=browse).pack(side="left", padx=(6, 0))

        for title, var in (
            (t("trade_folder_label"), folder_var),
            (t("trade_att_folder"), att_var),
            (t("trade_hotkey"), hotkey_var),
        ):
            self._label(body, title).pack(fill="x", pady=(12, 4))
            self._entry(body, var).pack(fill="x")

        def save() -> None:
            cfg = load_config()
            cfg["trade_vault_path"] = vault_var.get().strip()
            cfg["trade_folder"] = folder_var.get().strip().strip("/\\")
            cfg["trade_attachments_folder"] = att_var.get().strip().strip("/\\")
            old_hotkey = str(cfg.get("trade_hotkey") or "")
            cfg["trade_hotkey"] = hotkey_var.get().strip().lower() or "ctrl+alt+t"
            save_config(cfg)
            dialog.destroy()
            self._refresh_stats()
            if cfg["trade_hotkey"] != old_hotkey and self.on_hotkey_changed:
                self.on_hotkey_changed()

        ctk.CTkButton(
            body, text=t("save"), height=36, fg_color=YELLOW, hover_color="#d9a70a", text_color=BG,
            font=ctk.CTkFont(weight="bold"), command=save,
        ).pack(fill="x", pady=(18, 0))
        dialog.after(250, dialog.lift)

    on_hotkey_changed: Callable[[], None] | None = None

"""
Окно рисования для заметки.

Перо, ластик, фигуры, заливка, фон из скриншота, отмена/повтор.
Готовый рисунок вставляется в заметку как картинка.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable

import customtkinter as ctk
import tkinter as tk
from PIL import Image, ImageDraw, ImageGrab, ImageTk

from ui_icon import apply_window_icon

# Палитра цветов для кисти
COLORS = [
    ("#111111", "Black"),
    ("#ffffff", "White"),
    ("#e74c3c", "Red"),
    ("#2980b9", "Blue"),
    ("#27ae60", "Green"),
    ("#8e44ad", "Purple"),
    ("#f39c12", "Orange"),
    ("#f1c40f", "Yellow"),
]

# Размер холста в пикселях
CANVAS_W = 720
CANVAS_H = 420
BG_RGB = (255, 255, 255)
BG_HEX = "#ffffff"

# Stable tool ids (UI labels come from i18n.paint_tools())
TOOL_IDS = ["pen", "eraser", "line", "rect", "oval", "fill"]


@dataclass
class HistoryEntry:
    """Шаг истории: либо фигуры на холсте, либо смена всей картинки (заливка/очистка/скрин)."""

    item_ids: list[int] = field(default_factory=list)
    before: Image.Image | None = None
    after: Image.Image | None = None


def drawing_filename(now: datetime | None = None) -> str:
    """Имя файла для сохранённого рисунка."""
    stamp = (now or datetime.now()).strftime("%Y-%m-%d %H-%M-%S")
    return f"Drawing {stamp}.png"


def _hex_to_rgb(color: str) -> tuple[int, int, int]:
    """Переводит цвет #RRGGBB в тройку чисел (R, G, B)."""
    c = color.lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)


def flood_fill(
    img: Image.Image,
    x: int,
    y: int,
    new_color: tuple[int, int, int],
    tol: int = 24,
) -> Image.Image:
    """Заливка области цветом (как ведёрко в Paint)."""
    work = img.convert("RGB")
    w, h = work.size
    if not (0 <= x < w and 0 <= y < h):
        return work
    px = work.load()
    assert px is not None
    target = px[x, y]
    if target == new_color:
        return work

    def match(c: tuple[int, int, int]) -> bool:
        return all(abs(c[i] - target[i]) <= tol for i in range(3))

    stack = [(x, y)]
    while stack:
        cx, cy = stack.pop()
        if not (0 <= cx < w and 0 <= cy < h):
            continue
        if not match(px[cx, cy]):
            continue
        px[cx, cy] = new_color
        stack.append((cx + 1, cy))
        stack.append((cx - 1, cy))
        stack.append((cx, cy + 1))
        stack.append((cx, cy - 1))
    return work


def composite_canvas(
    base: Image.Image,
    canvas: tk.Canvas,
    width: int,
    height: int,
) -> Image.Image:
    """Склеивает фон и нарисованные линии/фигуры в одну картинку."""
    img = base.resize((width, height), Image.Resampling.LANCZOS).convert("RGB")
    draw = ImageDraw.Draw(img)

    for item in canvas.find_all():
        tags = canvas.gettags(item)
        if "bg" in tags:
            continue
        kind = canvas.type(item)
        coords = canvas.coords(item)
        if kind == "line" and len(coords) >= 4:
            color = canvas.itemcget(item, "fill") or "#000000"
            try:
                width_px = max(1, int(float(canvas.itemcget(item, "width") or 2)))
            except ValueError:
                width_px = 2
            points = list(zip(coords[0::2], coords[1::2]))
            draw.line(points, fill=color, width=width_px, joint="curve")
            r = max(1, width_px // 2)
            for x, y in (points[0], points[-1]):
                draw.ellipse((x - r, y - r, x + r, y + r), fill=color)
        elif kind == "rectangle" and len(coords) >= 4:
            outline = canvas.itemcget(item, "outline") or "#000000"
            try:
                width_px = max(1, int(float(canvas.itemcget(item, "width") or 2)))
            except ValueError:
                width_px = 2
            draw.rectangle(coords[:4], outline=outline, width=width_px)
        elif kind == "oval" and len(coords) >= 4:
            outline = canvas.itemcget(item, "outline") or "#000000"
            try:
                width_px = max(1, int(float(canvas.itemcget(item, "width") or 2)))
            except ValueError:
                width_px = 2
            draw.ellipse(coords[:4], outline=outline, width=width_px)
    return img


# Старое имя для тестов
def canvas_to_image(canvas: tk.Canvas, width: int, height: int) -> Image.Image:
    """Превращает холст в картинку (белый фон + рисунок)."""
    blank = Image.new("RGB", (width, height), BG_RGB)
    return composite_canvas(blank, canvas, width, height)


class PaintWindow:
    """Окно рисования. По «Вставить в заметку» отдаёт картинку в заметку."""

    def __init__(
        self,
        parent: ctk.CTk | ctk.CTkToplevel,
        on_done: Callable[[Image.Image], None] | None = None,
        *,
        with_screenshot: bool = False,
    ) -> None:
        from i18n import paint_tools, t

        self.on_done = on_done
        self._parent = parent
        self._color = COLORS[0][0]
        labels = paint_tools()
        self._id_by_label = dict(zip(labels, TOOL_IDS))
        self._label_by_id = dict(zip(TOOL_IDS, labels))
        self._tool = TOOL_IDS[0]
        self._thickness = 4
        self._history: list[HistoryEntry] = []  # отмена
        self._redo: list[HistoryEntry] = []  # повтор
        self._current_ids: list[int] = []
        self._last: tuple[float, float] | None = None
        self._start: tuple[float, float] | None = None
        self._preview_id: int | None = None
        self._color_buttons: dict[str, ctk.CTkButton] = {}
        self._photo: ImageTk.PhotoImage | None = None
        self._bg_id: int | None = None

        base = Image.new("RGB", (CANVAS_W, CANVAS_H), BG_RGB)
        if with_screenshot:
            grabbed = self._grab_screenshot()
            if grabbed is not None:
                base = grabbed
        self._base = base

        self.dialog = ctk.CTkToplevel(parent)
        self.dialog.title(t("paint_title"))
        self.dialog.geometry("780x580")
        self.dialog.minsize(680, 520)
        self.dialog.attributes("-topmost", True)
        self.dialog.transient(parent)
        self.dialog.grab_set()
        self.dialog.focus_force()
        apply_window_icon(self.dialog)

        # Строка инструментов (перо, ластик, фигуры…)
        row1 = ctk.CTkFrame(self.dialog, fg_color="transparent")
        row1.pack(fill="x", padx=12, pady=(12, 4))

        self._tool_var = ctk.StringVar(value=labels[0])
        ctk.CTkSegmentedButton(
            row1,
            values=labels,
            variable=self._tool_var,
            command=self._on_tool,
            height=28,
        ).pack(side="left", fill="x", expand=True)

        # Цвета, толщина, undo/redo, скрин, вставка фона
        row2 = ctk.CTkFrame(self.dialog, fg_color="transparent")
        row2.pack(fill="x", padx=12, pady=(4, 4))

        colors_frame = ctk.CTkFrame(row2, fg_color="#2a2a2a", corner_radius=8)
        colors_frame.pack(side="left", padx=(0, 10))
        for hex_color, _label in COLORS:
            btn = ctk.CTkButton(
                colors_frame,
                text="",
                width=30,
                height=30,
                fg_color=hex_color,
                hover_color=hex_color,
                corner_radius=6,
                border_width=2,
                border_color="#888888",
                command=lambda c=hex_color: self._set_color(c),
            )
            btn.pack(side="left", padx=4, pady=4)
            self._color_buttons[hex_color] = btn
        self._refresh_color_selection()

        ctk.CTkLabel(row2, text=t("paint_size")).pack(side="left", padx=(4, 4))
        self._thick_label = ctk.CTkLabel(row2, text="4 px", width=44)
        self._thick_label.pack(side="left")
        self._thick = ctk.CTkSlider(
            row2,
            from_=1,
            to=40,
            number_of_steps=39,
            width=140,
            command=self._on_thick,
        )
        self._thick.set(self._thickness)
        self._thick.pack(side="left", padx=(4, 8))

        ctk.CTkButton(row2, text="Redo", width=60, command=self._redo_action).pack(
            side="right", padx=(4, 0)
        )
        ctk.CTkButton(row2, text="Undo", width=60, command=self._undo).pack(side="right")
        ctk.CTkButton(row2, text=t("paint_clear"), width=80, command=self._clear).pack(
            side="right", padx=(0, 4)
        )
        ctk.CTkButton(
            row2,
            text=t("paint_paste"),
            width=80,
            command=self._paste_background,
            fg_color="#333333",
            hover_color="#444444",
        ).pack(side="right", padx=(0, 4))
        ctk.CTkButton(
            row2,
            text=t("paint_shot"),
            width=70,
            command=self._rescreenshot,
            fg_color="#333333",
            hover_color="#444444",
        ).pack(side="right", padx=(0, 4))

        canvas_frame = ctk.CTkFrame(self.dialog, fg_color="#2a2a2a", corner_radius=8)
        canvas_frame.pack(fill="both", expand=True, padx=12, pady=6)

        # Сам холст, по которому рисуют мышью
        self.canvas = tk.Canvas(
            canvas_frame,
            width=CANVAS_W,
            height=CANVAS_H,
            bg=BG_HEX,
            highlightthickness=1,
            highlightbackground="#555555",
            cursor="pencil",
        )
        self.canvas.pack(padx=8, pady=8, expand=True)
        self._paint_bg()

        self.canvas.bind("<ButtonPress-1>", self._down)
        self.canvas.bind("<B1-Motion>", self._move)
        self.canvas.bind("<ButtonRelease-1>", self._up)
        def _paste_event(_e=None):
            self._paste_background()
            return "break"

        for seq in ("<Control-v>", "<Control-V>"):
            self.dialog.bind(seq, _paste_event)
            self.canvas.bind(seq, _paste_event)
        self.dialog.bind_all("<Control-v>", _paste_event)

        footer = ctk.CTkFrame(self.dialog, fg_color="transparent")
        footer.pack(fill="x", padx=12, pady=(6, 12))
        ctk.CTkLabel(
            footer,
            text=t("paint_hint"),
            text_color="#666666",
            font=ctk.CTkFont(size=11),
        ).pack(side="left")
        ctk.CTkButton(footer, text=t("paint_cancel"), width=100, command=self.dialog.destroy).pack(
            side="right"
        )
        ctk.CTkButton(
            footer,
            text=t("paint_insert"),
            width=160,
            command=self._insert,
            fg_color="#3878fa",
            hover_color="#2f66d8",
        ).pack(side="right", padx=(0, 8))

    @staticmethod
    def _fit_image(img: Image.Image, tw: int, th: int) -> Image.Image:
        """Вписывает картинку в размер холста с полями."""
        img = img.convert("RGB")
        src_w, src_h = img.size
        scale = min(tw / src_w, th / src_h)
        nw, nh = max(1, int(src_w * scale)), max(1, int(src_h * scale))
        resized = img.resize((nw, nh), Image.Resampling.LANCZOS)
        canvas = Image.new("RGB", (tw, th), BG_RGB)
        canvas.paste(resized, ((tw - nw) // 2, (th - nh) // 2))
        return canvas

    def _paint_bg(self) -> None:
        """Рисует фоновую картинку на холсте."""
        w = int(self.canvas.winfo_width()) or CANVAS_W
        h = int(self.canvas.winfo_height()) or CANVAS_H
        # При первом показе размер может быть 1 — берём значения по умолчанию
        if w < 10:
            w = CANVAS_W
        if h < 10:
            h = CANVAS_H
        shown = self._base.resize((w, h), Image.Resampling.LANCZOS)
        self._photo = ImageTk.PhotoImage(shown)
        if self._bg_id is not None:
            try:
                self.canvas.delete(self._bg_id)
            except tk.TclError:
                pass
        self._bg_id = self.canvas.create_image(0, 0, anchor="nw", image=self._photo, tags=("bg",))
        self.canvas.tag_lower("bg")

    def _pen_width(self) -> int:
        """Толщина линии; у ластика чуть больше."""
        if self._tool == "eraser":
            return max(self._thickness * 2, self._thickness + 6)
        return self._thickness

    def _draw_color(self) -> str:
        """Цвет рисования; ластик = цвет фона."""
        if self._tool == "eraser":
            return BG_HEX
        return self._color

    def _on_tool(self, value: str) -> None:
        """Смена инструмента на панели."""
        self._tool = self._id_by_label.get(value, "pen")
        cursors = {
            "pen": "pencil",
            "eraser": "dotbox",
            "line": "crosshair",
            "rect": "crosshair",
            "oval": "crosshair",
            "fill": "spraycan",
        }
        self.canvas.configure(cursor=cursors.get(self._tool, "arrow"))

    def _set_color(self, color: str) -> None:
        """Выбор цвета кисти."""
        self._color = color
        if self._tool == "eraser":
            self._tool = "pen"
            pen_label = self._label_by_id["pen"]
            self._tool_var.set(pen_label)
            self._on_tool(pen_label)
        self._refresh_color_selection()

    def _refresh_color_selection(self) -> None:
        """Подсвечивает выбранный цвет на палитре."""
        for hex_color, btn in self._color_buttons.items():
            selected = hex_color.lower() == self._color.lower()
            # Рамка всегда видна; у выбранного — яркий акцент
            if selected:
                border = "#3878fa"
                width = 3
            elif hex_color.lower() in {"#111111", "#000000"}:
                border = "#dddddd"
                width = 2
            elif hex_color.lower() == "#ffffff":
                border = "#888888"
                width = 2
            else:
                border = "#666666"
                width = 2
            btn.configure(border_color=border, border_width=width)

    def _on_thick(self, value: float) -> None:
        """Ползунок толщины линии."""
        self._thickness = max(1, int(round(float(value))))
        self._thick_label.configure(text=f"{self._thickness} px")

    def _push_items(self, ids: list[int]) -> None:
        """Запоминает нарисованные объекты для Undo."""
        if not ids:
            return
        self._history.append(HistoryEntry(item_ids=list(ids)))
        self._redo.clear()

    def _push_raster(self, before: Image.Image, after: Image.Image) -> None:
        """Запоминает смену всей картинки (заливка/очистка) для Undo."""
        self._history.append(HistoryEntry(before=before.copy(), after=after.copy()))
        self._redo.clear()

    def _down(self, event: tk.Event) -> None:
        """Начало штриха / фигуры при нажатии мыши."""
        self._start = (event.x, event.y)
        self._last = (event.x, event.y)
        self._current_ids = []
        self._preview_id = None

        if self._tool == "fill":
            self._do_fill(event.x, event.y)
            self._start = None
            return

        if self._tool in {"pen", "eraser"}:
            # Dot at click
            r = max(1, self._pen_width() // 2)
            color = self._draw_color()
            item = self.canvas.create_oval(
                event.x - r,
                event.y - r,
                event.x + r,
                event.y + r,
                fill=color,
                outline=color,
                tags=("ink",),
            )
            self._current_ids.append(item)

    def _move(self, event: tk.Event) -> None:
        """Продолжение рисования при движении мыши."""
        if self._start is None or self._tool == "fill":
            return

        if self._tool in {"pen", "eraser"}:
            if self._last is None:
                return
            x0, y0 = self._last
            item = self.canvas.create_line(
                x0,
                y0,
                event.x,
                event.y,
                fill=self._draw_color(),
                width=self._pen_width(),
                capstyle=tk.ROUND,
                joinstyle=tk.ROUND,
                smooth=True,
                tags=("ink",),
            )
            self._current_ids.append(item)
            self._last = (event.x, event.y)
            return

        # Shape preview
        if self._preview_id is not None:
            self.canvas.delete(self._preview_id)
        x0, y0 = self._start
        color = self._color
        width = self._pen_width()
        if self._tool == "line":
            self._preview_id = self.canvas.create_line(
                x0, y0, event.x, event.y, fill=color, width=width, tags=("ink", "preview")
            )
        elif self._tool == "rect":
            self._preview_id = self.canvas.create_rectangle(
                x0, y0, event.x, event.y, outline=color, width=width, tags=("ink", "preview")
            )
        elif self._tool == "oval":
            self._preview_id = self.canvas.create_oval(
                x0, y0, event.x, event.y, outline=color, width=width, tags=("ink", "preview")
            )

    def _up(self, event: tk.Event) -> None:
        """Завершение штриха / фигуры при отпускании мыши."""
        if self._tool == "fill":
            return

        if self._tool in {"pen", "eraser"}:
            self._push_items(self._current_ids)
            self._current_ids = []
            self._last = None
            self._start = None
            return

        if self._preview_id is not None:
            # Фиксируем превью как настоящий объект на холсте
            self.canvas.dtag(self._preview_id, "preview")
            self._push_items([self._preview_id])
            self._preview_id = None
        self._start = None
        self._last = None

    def _do_fill(self, x: int, y: int) -> None:
        """Заливка области цветом в точке клика."""
        w = int(self.canvas.winfo_width()) or CANVAS_W
        h = int(self.canvas.winfo_height()) or CANVAS_H
        before = composite_canvas(self._base, self.canvas, w, h)
        after = flood_fill(before, int(x), int(y), _hex_to_rgb(self._color))
        self._push_raster(before, after)
        self._apply_raster(after)

    def _apply_raster(self, img: Image.Image) -> None:
        """Делает картинку новым фоном и убирает векторные штрихи."""
        self._base = img.copy()
        for item in self.canvas.find_withtag("ink"):
            self.canvas.delete(item)
        self._paint_bg()

    def _undo(self) -> None:
        """Отменить последний шаг."""
        if not self._history:
            return
        entry = self._history.pop()
        if entry.before is not None and entry.after is not None:
            self._apply_raster(entry.before)
            self._redo.append(entry)
            return
        # Прячем объекты (id оставляем для Redo)
        for item_id in entry.item_ids:
            try:
                self.canvas.itemconfigure(item_id, state="hidden")
            except tk.TclError:
                pass
        self._redo.append(entry)

    def _redo_action(self) -> None:
        """Повторить отменённый шаг."""
        if not self._redo:
            return
        entry = self._redo.pop()
        if entry.before is not None and entry.after is not None:
            self._apply_raster(entry.after)
            self._history.append(entry)
            return
        for item_id in entry.item_ids:
            try:
                self.canvas.itemconfigure(item_id, state="normal")
            except tk.TclError:
                pass
        self._history.append(entry)

    def _clear(self) -> None:
        """Очистить холст."""
        w = int(self.canvas.winfo_width()) or CANVAS_W
        h = int(self.canvas.winfo_height()) or CANVAS_H
        before = composite_canvas(self._base, self.canvas, w, h)
        after = Image.new("RGB", (w, h), BG_RGB)
        self._push_raster(before, after)
        self._apply_raster(after)

    def _grab_screenshot(self) -> Image.Image | None:
        """Снимает скриншот экрана для фона (без окна рисования)."""
        try:
            parent = self._parent
            was_withdrawn = parent.state() == "withdrawn"
            parent.withdraw()
            parent.update_idletasks()
            if hasattr(self, "dialog"):
                try:
                    self.dialog.withdraw()
                except Exception:  # noqa: BLE001
                    pass
            time.sleep(0.12)
            shot = ImageGrab.grab()
            if not was_withdrawn:
                parent.deiconify()
                parent.lift()
            if hasattr(self, "dialog"):
                try:
                    self.dialog.deiconify()
                    self.dialog.lift()
                    self.dialog.grab_set()
                except Exception:  # noqa: BLE001
                    pass
            return self._fit_image(shot, CANVAS_W, CANVAS_H)
        except Exception:  # noqa: BLE001
            try:
                self._parent.deiconify()
            except Exception:  # noqa: BLE001
                pass
            return None

    def _set_background(self, img: Image.Image) -> None:
        """Ставит картинку фоном холста."""
        w = int(self.canvas.winfo_width()) or CANVAS_W
        h = int(self.canvas.winfo_height()) or CANVAS_H
        if w < 10:
            w = CANVAS_W
        if h < 10:
            h = CANVAS_H
        before = composite_canvas(self._base, self.canvas, w, h)
        after = self._fit_image(img, w, h)
        self._push_raster(before, after)
        self._apply_raster(after)

    def _paste_background(self) -> str:
        """Paste clipboard image as canvas background."""
        from clipboard_image import grab_clipboard_image

        img = grab_clipboard_image()
        if img is None:
            return "break"
        self._set_background(img)
        return "break"

    def _rescreenshot(self) -> None:
        """Делает новый скриншот и ставит его фоном."""
        grabbed = self._grab_screenshot()
        if grabbed is None:
            return
        self._set_background(grabbed)

    def _insert(self) -> None:
        """Собрать картинку и передать её в заметку."""
        w = int(self.canvas.winfo_width()) or CANVAS_W
        h = int(self.canvas.winfo_height()) or CANVAS_H
        if w < 10:
            w = CANVAS_W
        if h < 10:
            h = CANVAS_H
        image = composite_canvas(self._base, self.canvas, w, h)
        if self.on_done:
            self.on_done(image)
        self.dialog.destroy()


def open_paint(
    parent: ctk.CTk | ctk.CTkToplevel,
    on_done: Callable[[Image.Image], None] | None = None,
    *,
    with_screenshot: bool = False,
) -> PaintWindow:
    """Открывает окно рисования; готовый рисунок уходит в on_done."""
    return PaintWindow(parent, on_done=on_done, with_screenshot=with_screenshot)

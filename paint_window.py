"""Paint dialog: pen, eraser, shapes, fill, screenshot bg, undo/redo → PIL Image."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable

import customtkinter as ctk
import tkinter as tk
from PIL import Image, ImageDraw, ImageGrab, ImageTk

from ui_icon import apply_window_icon

COLORS = [
    ("#111111", "Чёрный"),
    ("#ffffff", "Белый"),
    ("#e74c3c", "Красный"),
    ("#2980b9", "Синий"),
    ("#27ae60", "Зелёный"),
    ("#8e44ad", "Фиолет"),
    ("#f39c12", "Оранж"),
    ("#f1c40f", "Жёлтый"),
]

CANVAS_W = 720
CANVAS_H = 420
BG_RGB = (255, 255, 255)
BG_HEX = "#ffffff"

TOOLS = ["Перо", "Ластик", "Линия", "Прямоуг", "Круг", "Заливка"]


@dataclass
class HistoryEntry:
    """Either canvas item ids, or a full raster swap (fill / clear / screenshot bake)."""

    item_ids: list[int] = field(default_factory=list)
    before: Image.Image | None = None
    after: Image.Image | None = None


def drawing_filename(now: datetime | None = None) -> str:
    stamp = (now or datetime.now()).strftime("%Y-%m-%d %H-%M-%S")
    return f"Drawing {stamp}.png"


def _hex_to_rgb(color: str) -> tuple[int, int, int]:
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
    """Bucket fill on RGB image; returns filled copy/work image."""
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
    """Draw canvas vector items over base image → RGB."""
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


# Back-compat name used by tests
def canvas_to_image(canvas: tk.Canvas, width: int, height: int) -> Image.Image:
    blank = Image.new("RGB", (width, height), BG_RGB)
    return composite_canvas(blank, canvas, width, height)


class PaintWindow:
    """Modal paint UI. Calls on_done(PIL.Image) when user inserts into the note."""

    def __init__(
        self,
        parent: ctk.CTk | ctk.CTkToplevel,
        on_done: Callable[[Image.Image], None] | None = None,
        *,
        with_screenshot: bool = False,
    ) -> None:
        self.on_done = on_done
        self._parent = parent
        self._color = COLORS[0][0]
        self._tool = "Перо"
        self._thickness = 4
        self._history: list[HistoryEntry] = []
        self._redo: list[HistoryEntry] = []
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
        self.dialog.title("Рисунок")
        self.dialog.geometry("780x580")
        self.dialog.minsize(680, 520)
        self.dialog.attributes("-topmost", True)
        self.dialog.transient(parent)
        self.dialog.grab_set()
        self.dialog.focus_force()
        apply_window_icon(self.dialog)

        row1 = ctk.CTkFrame(self.dialog, fg_color="transparent")
        row1.pack(fill="x", padx=12, pady=(12, 4))

        self._tool_var = ctk.StringVar(value="Перо")
        ctk.CTkSegmentedButton(
            row1,
            values=TOOLS,
            variable=self._tool_var,
            command=self._on_tool,
            height=28,
        ).pack(side="left", fill="x", expand=True)

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

        ctk.CTkLabel(row2, text="Толщина").pack(side="left", padx=(4, 4))
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
        ctk.CTkButton(row2, text="Очистить", width=80, command=self._clear).pack(
            side="right", padx=(0, 4)
        )
        ctk.CTkButton(
            row2,
            text="Вставить",
            width=80,
            command=self._paste_background,
            fg_color="#333333",
            hover_color="#444444",
        ).pack(side="right", padx=(0, 4))
        ctk.CTkButton(
            row2,
            text="Скрин",
            width=70,
            command=self._rescreenshot,
            fg_color="#333333",
            hover_color="#444444",
        ).pack(side="right", padx=(0, 4))

        canvas_frame = ctk.CTkFrame(self.dialog, fg_color="#2a2a2a", corner_radius=8)
        canvas_frame.pack(fill="both", expand=True, padx=12, pady=6)

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
        self.dialog.bind("<Control-v>", lambda _e: self._paste_background())
        self.dialog.bind("<Control-V>", lambda _e: self._paste_background())
        self.canvas.bind("<Control-v>", lambda _e: self._paste_background())
        self.canvas.bind("<Control-V>", lambda _e: self._paste_background())

        footer = ctk.CTkFrame(self.dialog, fg_color="transparent")
        footer.pack(fill="x", padx=12, pady=(6, 12))
        ctk.CTkLabel(
            footer,
            text="По умолчанию пустой холст · Скрин / Вставить (Ctrl+V) — фон",
            text_color="#666666",
            font=ctk.CTkFont(size=11),
        ).pack(side="left")
        ctk.CTkButton(footer, text="Отмена", width=100, command=self.dialog.destroy).pack(
            side="right"
        )
        ctk.CTkButton(
            footer,
            text="Вставить в заметку",
            width=160,
            command=self._insert,
            fg_color="#3878fa",
            hover_color="#2f66d8",
        ).pack(side="right", padx=(0, 8))

    @staticmethod
    def _fit_image(img: Image.Image, tw: int, th: int) -> Image.Image:
        img = img.convert("RGB")
        src_w, src_h = img.size
        scale = min(tw / src_w, th / src_h)
        nw, nh = max(1, int(src_w * scale)), max(1, int(src_h * scale))
        resized = img.resize((nw, nh), Image.Resampling.LANCZOS)
        canvas = Image.new("RGB", (tw, th), BG_RGB)
        canvas.paste(resized, ((tw - nw) // 2, (th - nh) // 2))
        return canvas

    def _paint_bg(self) -> None:
        w = int(self.canvas.winfo_width()) or CANVAS_W
        h = int(self.canvas.winfo_height()) or CANVAS_H
        # On first pack winfo may be 1 — use defaults
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
        if self._tool == "Ластик":
            return max(self._thickness * 2, self._thickness + 6)
        return self._thickness

    def _draw_color(self) -> str:
        if self._tool == "Ластик":
            return BG_HEX
        return self._color

    def _on_tool(self, value: str) -> None:
        self._tool = value
        cursors = {
            "Перо": "pencil",
            "Ластик": "dotbox",
            "Линия": "crosshair",
            "Прямоуг": "crosshair",
            "Круг": "crosshair",
            "Заливка": "spraycan",
        }
        self.canvas.configure(cursor=cursors.get(value, "arrow"))

    def _set_color(self, color: str) -> None:
        self._color = color
        if self._tool == "Ластик":
            self._tool = "Перо"
            self._tool_var.set("Перо")
            self._on_tool("Перо")
        self._refresh_color_selection()

    def _refresh_color_selection(self) -> None:
        for hex_color, btn in self._color_buttons.items():
            selected = hex_color.lower() == self._color.lower()
            # Always visible ring; selected = bright accent
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
        self._thickness = max(1, int(round(float(value))))
        self._thick_label.configure(text=f"{self._thickness} px")

    def _push_items(self, ids: list[int]) -> None:
        if not ids:
            return
        self._history.append(HistoryEntry(item_ids=list(ids)))
        self._redo.clear()

    def _push_raster(self, before: Image.Image, after: Image.Image) -> None:
        self._history.append(HistoryEntry(before=before.copy(), after=after.copy()))
        self._redo.clear()

    def _down(self, event: tk.Event) -> None:
        self._start = (event.x, event.y)
        self._last = (event.x, event.y)
        self._current_ids = []
        self._preview_id = None

        if self._tool == "Заливка":
            self._do_fill(event.x, event.y)
            self._start = None
            return

        if self._tool in {"Перо", "Ластик"}:
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
        if self._start is None or self._tool == "Заливка":
            return

        if self._tool in {"Перо", "Ластик"}:
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
        if self._tool == "Линия":
            self._preview_id = self.canvas.create_line(
                x0, y0, event.x, event.y, fill=color, width=width, tags=("ink", "preview")
            )
        elif self._tool == "Прямоуг":
            self._preview_id = self.canvas.create_rectangle(
                x0, y0, event.x, event.y, outline=color, width=width, tags=("ink", "preview")
            )
        elif self._tool == "Круг":
            self._preview_id = self.canvas.create_oval(
                x0, y0, event.x, event.y, outline=color, width=width, tags=("ink", "preview")
            )

    def _up(self, event: tk.Event) -> None:
        if self._tool == "Заливка":
            return

        if self._tool in {"Перо", "Ластик"}:
            self._push_items(self._current_ids)
            self._current_ids = []
            self._last = None
            self._start = None
            return

        if self._preview_id is not None:
            # Commit preview as real item (remove preview tag conceptually — already ink)
            self.canvas.dtag(self._preview_id, "preview")
            self._push_items([self._preview_id])
            self._preview_id = None
        self._start = None
        self._last = None

    def _do_fill(self, x: int, y: int) -> None:
        w = int(self.canvas.winfo_width()) or CANVAS_W
        h = int(self.canvas.winfo_height()) or CANVAS_H
        before = composite_canvas(self._base, self.canvas, w, h)
        after = flood_fill(before, int(x), int(y), _hex_to_rgb(self._color))
        self._push_raster(before, after)
        self._apply_raster(after)

    def _apply_raster(self, img: Image.Image) -> None:
        """Bake image as new base and clear vector ink."""
        self._base = img.copy()
        for item in self.canvas.find_withtag("ink"):
            self.canvas.delete(item)
        self._paint_bg()

    def _undo(self) -> None:
        if not self._history:
            return
        entry = self._history.pop()
        if entry.before is not None and entry.after is not None:
            self._apply_raster(entry.before)
            self._redo.append(entry)
            return
        # Hide items (keep ids for redo)
        for item_id in entry.item_ids:
            try:
                self.canvas.itemconfigure(item_id, state="hidden")
            except tk.TclError:
                pass
        self._redo.append(entry)

    def _redo_action(self) -> None:
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
        w = int(self.canvas.winfo_width()) or CANVAS_W
        h = int(self.canvas.winfo_height()) or CANVAS_H
        before = composite_canvas(self._base, self.canvas, w, h)
        after = Image.new("RGB", (w, h), BG_RGB)
        self._push_raster(before, after)
        self._apply_raster(after)

    def _grab_screenshot(self) -> Image.Image | None:
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
        """Paste clipboard image (or screenshot file list) as canvas background."""
        clipped = ImageGrab.grabclipboard()
        img: Image.Image | None = None
        if isinstance(clipped, Image.Image):
            img = clipped
        elif isinstance(clipped, list) and clipped:
            try:
                img = Image.open(clipped[0]).convert("RGB")
            except Exception:  # noqa: BLE001
                img = None
        if img is None:
            return "break"
        self._set_background(img)
        return "break"

    def _rescreenshot(self) -> None:
        grabbed = self._grab_screenshot()
        if grabbed is None:
            return
        self._set_background(grabbed)

    def _insert(self) -> None:
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
    return PaintWindow(parent, on_done=on_done, with_screenshot=with_screenshot)

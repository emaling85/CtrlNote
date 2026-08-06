"""
Автотесты окна рисования и преобразования холста в картинку.
"""

from __future__ import annotations

import tkinter as tk
import unittest
from datetime import datetime

from PIL import Image

from paint_window import canvas_to_image, drawing_filename, flood_fill


class DrawingFilenameTests(unittest.TestCase):
    def test_name(self) -> None:
        name = drawing_filename(datetime(2026, 8, 3, 15, 55, 1))
        self.assertEqual(name, "Drawing 2026-08-03 15-55-01.png")


class CanvasExportTests(unittest.TestCase):
    def test_export_has_ink(self) -> None:
        root = tk.Tk()
        root.withdraw()
        canvas = tk.Canvas(root, width=100, height=80, bg="#ffffff")
        canvas.create_line(10, 10, 90, 70, fill="#111111", width=4, tags=("ink",))
        img = canvas_to_image(canvas, 100, 80)
        root.destroy()
        self.assertEqual(img.size, (100, 80))
        extrema = img.getextrema()
        self.assertTrue(any(lo < 250 for lo, _hi in extrema))

    def test_export_shapes(self) -> None:
        root = tk.Tk()
        root.withdraw()
        canvas = tk.Canvas(root, width=120, height=100, bg="#ffffff")
        canvas.create_rectangle(10, 10, 50, 40, outline="#e74c3c", width=3, tags=("ink",))
        canvas.create_oval(60, 20, 110, 80, outline="#2980b9", width=3, tags=("ink",))
        img = canvas_to_image(canvas, 120, 100)
        root.destroy()
        self.assertEqual(img.size, (120, 100))
        self.assertTrue(any(pixel != (255, 255, 255) for pixel in img.getdata()))


class FloodFillTests(unittest.TestCase):
    def test_fill_center(self) -> None:
        img = Image.new("RGB", (20, 20), (255, 255, 255))
        out = flood_fill(img, 10, 10, (255, 0, 0), tol=0)
        self.assertEqual(out.getpixel((10, 10)), (255, 0, 0))
        self.assertEqual(out.getpixel((0, 0)), (255, 0, 0))


if __name__ == "__main__":
    unittest.main()

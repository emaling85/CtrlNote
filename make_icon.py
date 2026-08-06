"""
Генерация иконок CtrlNote.

Рисует гладкий значок (не пиксельный) и сохраняет PNG/ICO в assets.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageFilter

ASSETS = Path(__file__).resolve().parent / "assets"
BLUE = (56, 120, 250, 255)
WHITE = (255, 255, 255, 255)
BORDER = (255, 255, 255, 220)


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Подбирает системный шрифт для букв C и N на иконке."""
    px = max(10, int(size * 0.48))
    for name in (
        r"C:\Windows\Fonts\seguisb.ttf",
        r"C:\Windows\Fonts\segoeuib.ttf",
        r"C:\Windows\Fonts\arialbd.ttf",
        r"C:\Windows\Fonts\arial.ttf",
    ):
        if Path(name).exists():
            return ImageFont.truetype(name, px)
    return ImageFont.load_default()


def make_icon(size: int) -> Image.Image:
    """Рисует иконку в 4 раза крупнее, потом уменьшает — края получаются гладкими."""
    if size < 8:
        size = 8
    scale = 4
    big = size * scale
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    pad = max(scale, round(big * 0.06))
    radius = max(scale * 2, round(big * 0.22))
    box = (pad, pad, big - pad - 1, big - pad - 1)
    draw.rounded_rectangle(box, radius=radius, fill=BLUE)
    rim = max(scale, big // 48)
    draw.rounded_rectangle(box, radius=radius, outline=BORDER, width=rim)

    font = _font(big)
    gap = max(scale, big // 20)
    b0 = draw.textbbox((0, 0), "C", font=font)
    b1 = draw.textbbox((0, 0), "N", font=font)
    w0, h0 = b0[2] - b0[0], b0[3] - b0[1]
    w1, h1 = b1[2] - b1[0], b1[3] - b1[1]
    total_w = w0 + gap + w1
    total_h = max(h0, h1)
    x0 = (big - total_w) // 2 - b0[0]
    y = (big - total_h) // 2 - min(b0[1], b1[1]) - big // 40
    draw.text((x0, y), "C", font=font, fill=WHITE)
    draw.text((x0 + w0 + gap, y), "N", font=font, fill=WHITE)

    # Лёгкое размытие перед уменьшением — меньше «мерцания» на мелких размерах
    if size <= 32:
        img = img.filter(ImageFilter.GaussianBlur(radius=0.4 * scale / 4))

    out = img.resize((size, size), Image.Resampling.LANCZOS)
    return out


def export_all() -> None:
    """Создаёт icon.png, icon.ico и иконки для трея в папке assets."""
    ASSETS.mkdir(parents=True, exist_ok=True)
    master = make_icon(512)
    master.save(ASSETS / "icon.png", optimize=True)

    # ICO сразу нескольких размеров — для заголовка окна, exe и ярлыков
    sizes = [16, 20, 24, 32, 40, 48, 64, 128, 256]
    frames = [make_icon(s) for s in sizes]
    frames[-1].save(
        ASSETS / "icon.ico",
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=frames[:-1],
    )

    # Для трея: гладкая иконка 32px (pystray)
    make_icon(32).save(ASSETS / "icon-tray.png")
    # Для экранов с высоким DPI
    make_icon(64).save(ASSETS / "icon-tray@2x.png")
    print("exported", ASSETS)


if __name__ == "__main__":
    export_all()

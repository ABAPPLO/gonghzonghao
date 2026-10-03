#!/usr/bin/env python3
"""Figure kit: shared primitives for WeChat in-article infographics.

Style matches the pipeline cover: deep navy -> indigo, accent #3b5bfd.
Each article renders its own figures via a small script importing this kit,
so labels stay topic-specific while the look stays consistent.

All sizes are 2x (WeChat body displays ~677px wide).
"""
import pathlib

from PIL import Image, ImageDraw, ImageFilter

FONT_REG = "C:/Windows/Fonts/msyh.ttc"     # 微软雅黑
FONT_BOLD = "C:/Windows/Fonts/msyhbd.ttc"

PAL = {
    "bg1": "#0a0e23", "bg2": "#3b5bfd",
    "card": "#131b3f", "card_hi": "#22346f",
    "border": "#28305e", "border_hi": "#4c63d8",
    "accent": "#3b5bfd", "bright": "#a8bcff",
    "text": "#f0f3ff", "muted": "#8a93c9",
    "light_bg": "#f5f7ff", "light_card": "#ffffff",
    "light_border": "#e2e7f5", "light_text": "#1f2329", "light_muted": "#6b7280",
}

_font_cache: dict[tuple[int, bool], Image.FreeTypeFont] = {}

def font(size: int, bold: bool = False):
    key = (size, bold)
    if key not in _font_cache:
        from PIL import ImageFont
        _font_cache[key] = ImageFont.truetype(FONT_BOLD if bold else FONT_REG, size)
    return _font_cache[key]

def hex2rgb(s: str):
    s = s.lstrip("#")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))

def rgba(s: str, a: int = 255):
    return hex2rgb(s) + (a,)

def gradient(size, c1: str, c2: str) -> Image.Image:
    w, h = size
    small = Image.new("RGB", (96, 96))
    px = small.load()
    a, b = hex2rgb(c1), hex2rgb(c2)
    for y in range(96):
        for x in range(96):
            t = (x / 95 + y / 95) / 2
            px[x, y] = tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))
    return small.resize((w, h), Image.BICUBIC).convert("RGBA")

def glow_layer(size, draw_fn, blur: int) -> Image.Image:
    """Draw shapes on a transparent layer, blur, return it for compositing."""
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(layer))
    return layer.filter(ImageFilter.GaussianBlur(blur))

def dot_grid(img: Image.Image, step: int = 56, alpha: int = 22) -> Image.Image:
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for y in range(40, img.height, step):
        for x in range(40, img.width, step):
            d.ellipse([x - 2, y - 2, x + 2, y + 2], fill=(160, 180, 255, alpha))
    return Image.alpha_composite(img, layer)

def card(draw: ImageDraw.ImageDraw, box, radius=20, fill="#131b3f",
         outline="#28305e", width=2):
    draw.rounded_rectangle(box, radius=radius, fill=rgba(fill),
                           outline=rgba(outline), width=width)

def text(draw, xy, s, size, color, bold=False, anchor="la"):
    draw.text(xy, s, font=font(size, bold), fill=rgba(color), anchor=anchor)

def tw(draw, s, size, bold=False) -> float:
    return draw.textlength(s, font=font(size, bold))

def assert_fits(draw, s, size, max_w, bold=False, label=""):
    w = tw(draw, s, size, bold)
    assert w <= max_w, f"text overflow ({label or s}): {w:.0f} > {max_w}"

def save(img: Image.Image, path):
    pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(path, "PNG")
    print(f"OK -> {path} ({img.width}x{img.height})")

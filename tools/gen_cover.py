#!/usr/bin/env python3
"""Generate a clean tech-style WeChat cover (2.35:1) with Pillow.

Fallback cover generator for the content pipeline: deterministic,
no external service needed. Outputs 1800x766 (2x of 900x383).

Usage: python tools/gen_cover.py <output.png>
"""
import sys

from PIL import Image, ImageDraw, ImageFilter

W, H = 1800, 766

def lerp(a, b, t):
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))

def diagonal_gradient(size, c1, c2):
    w, h = size
    small = Image.new("RGB", (128, 128))
    px = small.load()
    for y in range(128):
        for x in range(128):
            px[x, y] = lerp(c1, c2, (x / 127 + y / 127) / 2)
    return small.resize((w, h), Image.BICUBIC)

def hex2rgb(s):
    s = s.lstrip("#")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))

def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else "cover.png"
    base = diagonal_gradient((W, H), hex2rgb("#0a0e23"), hex2rgb("#3b5bfd")).convert("RGBA")

    # subtle dot grid
    grid = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(grid)
    for gy in range(40, H, 56):
        for gx in range(40, W, 56):
            d.ellipse([gx - 2, gy - 2, gx + 2, gy + 2], fill=(160, 180, 255, 26))
    base = Image.alpha_composite(base, grid)

    # ambient glow orbs
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dg = ImageDraw.Draw(glow)
    dg.ellipse([W - 520, -260, W + 260, 420], fill=(124, 156, 255, 110))
    dg.ellipse([-300, H - 340, 420, H + 260], fill=(59, 91, 253, 120))
    glow = glow.filter(ImageFilter.GaussianBlur(120))
    base = Image.alpha_composite(base, glow)

    # leaderboard bars (ranking motif)
    bars = [
        (1290, "#a8bcff", 255),   # newly topped rank — brightest
        (1040, "#7b93ff", 220),
        (860,  "#5e77f2", 185),
        (690,  "#4a5fd4", 150),
        (520,  "#3a4aa8", 115),
    ]
    bar_h, gap, x0 = 62, 44, 170
    total_h = len(bars) * bar_h + (len(bars) - 1) * gap
    y = (H - total_h) // 2 - 10

    # glow under the top bar
    bar_glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(bar_glow).rounded_rectangle(
        [x0, y, x0 + bars[0][0], y + bar_h], radius=31, fill=(168, 188, 255, 160))
    bar_glow = bar_glow.filter(ImageFilter.GaussianBlur(26))
    base = Image.alpha_composite(base, bar_glow)

    d = ImageDraw.Draw(base)
    for width, color, alpha in bars:
        rgb = hex2rgb(color)
        d.rounded_rectangle([x0, y, x0 + width, y + bar_h], radius=31,
                            fill=rgb + (alpha,))
        # leading bright head on each bar
        d.rounded_rectangle([x0, y, x0 + 120, y + bar_h], radius=31,
                            fill=tuple(min(255, c + 40) for c in rgb) + (alpha,))
        y += bar_h + gap

    # glowing marker dot on the winning bar
    dot = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    top_bar_cy = (H - total_h) // 2 - 10 + bar_h // 2
    ImageDraw.Draw(dot).ellipse(
        [x0 + 1290 - 150 - 26, top_bar_cy - 26, x0 + 1290 - 150 + 26, top_bar_cy + 26],
        fill=(235, 242, 255, 255))
    dot = dot.filter(ImageFilter.GaussianBlur(2))
    halo = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(halo).ellipse(
        [x0 + 1290 - 150 - 60, top_bar_cy - 60, x0 + 1290 - 150 + 60, top_bar_cy + 60],
        fill=(180, 200, 255, 200))
    halo = halo.filter(ImageFilter.GaussianBlur(30))
    base = Image.alpha_composite(base, halo)
    base = Image.alpha_composite(base, dot)

    base.convert("RGB").save(out_path, "PNG")
    print(f"OK -> {out_path} ({W}x{H})")

if __name__ == "__main__":
    main()

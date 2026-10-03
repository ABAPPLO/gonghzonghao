#!/usr/bin/env python3
"""Render cover + in-article figures for 2026-09-18 AI手机元年 (run from repo root)."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "tools"))
from figure_kit import (PAL, card, dot_grid, glow_layer, gradient, rgba,
                        save, text, tw)

OUT = pathlib.Path(__file__).parent

def _phone(dr, cx, cy, w, h, outline="#8fa3f0", width=5, fill="#10173a"):
    """Rounded phone outline centered at (cx, cy)."""
    dr.rounded_rectangle([cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2],
                         radius=w // 5, fill=rgba(fill), outline=rgba(outline),
                         width=width)
    # camera dot
    dr.ellipse([cx - 7, cy - h / 2 + 22, cx + 7, cy - h / 2 + 36],
               fill=rgba("#6b7cc9"))

def _cloud(dr, cx, cy, scale=1.0, color="#9db4ff"):
    """Simple cloud icon from overlapping ellipses."""
    for dx, dy, rx, ry in [(-34, 6, 30, 22), (0, -12, 40, 30), (36, 8, 28, 20)]:
        dr.ellipse([cx + dx * scale - rx * scale, cy + dy * scale - ry * scale,
                    cx + dx * scale + rx * scale, cy + dy * scale + ry * scale],
                   fill=rgba(color))

def _chip(dr, cx, cy, size=44):
    dr.rounded_rectangle([cx - size, cy - size, cx + size, cy + size],
                         radius=8, fill=rgba(PAL["accent"]))
    for d in (-size - 14, 0, size + 14):
        dr.line([cx - size * 0.5, cy + d, cx + size * 0.5, cy + d],
                fill=rgba("#7b93ff"), width=4)
        dr.line([cx + d, cy - size * 0.5, cx + d, cy + size * 0.5],
                fill=rgba("#7b93ff"), width=4)

# ---------- cover: glowing phone with a neural screen ----------
def cover():
    from PIL import Image, ImageDraw
    W, H = 1800, 766
    img = gradient((W, H), PAL["bg1"], "#2a3fb0")
    img = dot_grid(img)

    px, py, pw, ph = W / 2, H / 2 - 10, 360, 600

    def _glow(dr):
        dr.ellipse([px - 240, py - 330, px + 240, py + 330],
                   fill=rgba("#7c9cff", 150))
    img = Image.alpha_composite(img, glow_layer((W, H), _glow, 70))

    d = ImageDraw.Draw(img)
    _phone(d, px, py, pw, ph, outline="#a8bcff", width=6)

    # neural net inside the screen
    pts = [(px - 85, py - 160), (px + 15, py - 180), (px + 85, py - 95),
           (px - 55, py - 65), (px + 55, py + 15), (px - 18, py + 95),
           (px + 88, py + 125), (px - 98, py + 145)]
    for i, a in enumerate(pts):
        for b in pts[i + 1:]:
            if (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 < 200 ** 2:
                d.line([a, b], fill=rgba("#5f7dff", 110), width=2)
    for x, y in pts:
        r = 12
        d.ellipse([x - r, y - r, x + r, y + r], fill=rgba("#cdd9ff"))
    _chip(d, px, py + 228, 28)

    save(img, OUT / "cover.png")

# ---------- fig 1: cloud AI vs on-device AI ----------
def fig1():
    from PIL import Image, ImageDraw
    W, H = 1600, 860
    img = gradient((W, H), PAL["bg1"], "#1a2455")
    img = dot_grid(img)
    d = ImageDraw.Draw(img)

    text(d, (W / 2, 72), "云端 AI vs 端侧 AI", 52, PAL["text"], True, "mm")
    text(d, (W / 2, 140), "模型在哪跑，决定了数据往哪走", 26, "#aab4e6", False, "mm")

    cw, ch, y = 660, 560, 200
    lx, rx = 110, W - 110 - cw

    # left: cloud
    card(d, [lx, y, lx + cw, y + ch], radius=24)
    text(d, (lx + cw / 2, y + 56), "云端 AI", 40, PAL["bright"], True, "mm")
    _phone(d, lx + 170, y + 250, 92, 170, outline="#7b8ecf", width=4)
    for sy, ay in ((y + 205, y + 178), (y + 250, y + 216), (y + 295, y + 254)):
        d.line([lx + 218, sy, lx + 352, ay], fill=rgba("#7b8ecf"), width=3)
        d.polygon([(lx + 364, ay), (lx + 350, ay - 8), (lx + 350, ay + 8)],
                  fill=rgba("#7b8ecf"))
    _cloud(d, lx + 470, y + 215, 1.0, "#9db4ff")
    for s in ("数据上传服务器", "依赖网络质量", "隐私存顾虑"):
        text(d, (lx + cw / 2, y + 396 + ["数据上传服务器", "依赖网络质量", "隐私存顾虑"].index(s) * 52),
             "· " + s, 30, PAL["muted"], False, "mm")

    # right: on-device
    card(d, [rx, y, rx + cw, y + ch], radius=24, fill=PAL["card_hi"],
         outline=PAL["border_hi"])
    text(d, (rx + cw / 2, y + 56), "端侧 AI", 40, PAL["bright"], True, "mm")

    def _glow(dr):
        dr.ellipse([rx + cw / 2 - 120, y + 200, rx + cw / 2 + 120, y + 440],
                   fill=rgba(PAL["accent"], 140))
    from PIL import Image as _I
    img = _I.alpha_composite(img, glow_layer((W, H), _glow, 30))
    d = ImageDraw.Draw(img)

    _phone(d, rx + cw / 2, y + 250, 130, 210, outline="#a8bcff", width=5,
           fill="#1a2455")
    _chip(d, rx + cw / 2, y + 250, 36)
    for s in ("本地运行不出设备", "断网弱网都可用", "低延迟响应快"):
        text(d, (rx + cw / 2, y + 396 + ["本地运行不出设备", "断网弱网都可用", "低延迟响应快"].index(s) * 52),
             "· " + s, 30, PAL["text"], False, "mm")

    # VS badge
    bx, by = W / 2, y + ch / 2
    d.ellipse([bx - 44, by - 44, bx + 44, by + 44], fill=rgba(PAL["accent"]))
    text(d, (bx, by), "VS", 34, "#ffffff", True, "mm")

    save(img, OUT / "fig1-cloud-vs-edge.png")

# ---------- fig 2: four key numbers (2x2 grid) ----------
def fig2():
    from PIL import Image, ImageDraw
    W, H = 1600, 860
    img = gradient((W, H), PAL["bg1"], "#1a2455")
    img = dot_grid(img)
    d = ImageDraw.Draw(img)

    text(d, (W / 2, 72), "2026 端侧 AI 的四个关键数字", 52, PAL["text"], True, "mm")

    cells = [
        ("45%", "支持生成式 AI 的机型", "占全球新机出货比例（Counterpoint 预测）"),
        ("7 家", "手机品牌完成合规备案", "苹果、华为、小米、OPPO、vivo 等"),
        ("+15%", "端侧 AI 翻译准确率提升", "OPPO × 联发科 MWC 2026 展示"),
        ("1.2 万亿", "端侧 AI 市场规模（元）", "机构预测，仍待杀手级应用引爆"),
    ]
    cw, ch, gx, gy, y0 = 660, 280, 60, 50, 170
    for i, (num, label, sub) in enumerate(cells):
        x = 110 + (i % 2) * (cw + gx)
        y = y0 + (i // 2) * (ch + gy)
        card(d, [x, y, x + cw, y + ch], radius=24,
             fill=PAL["card_hi"] if i == 0 else PAL["card"],
             outline=PAL["border_hi"] if i == 0 else PAL["border"])
        assert tw(d, num, 76, True) < cw - 60, num
        text(d, (x + 46, y + 78), num, 76, PAL["bright"], True, "lm")
        assert tw(d, label, 32, True) < cw - 60, label
        text(d, (x + 46, y + 168), label, 32, PAL["text"], True, "lm")
        assert tw(d, sub, 24) < cw - 60, sub
        text(d, (x + 46, y + 222), sub, 24, PAL["muted"], False, "lm")

    save(img, OUT / "fig2-numbers.png")

# ---------- fig 3: quote card ----------
def fig3():
    from PIL import Image, ImageDraw
    W, H = 1600, 560
    img = gradient((W, H), PAL["bg1"], "#233299")
    img = dot_grid(img)

    def _orb(dr):
        dr.ellipse([W - 420, -200, W + 200, 340], fill=rgba("#7c9cff", 90))
        dr.ellipse([-260, H - 260, 300, H + 200], fill=rgba(PAL["accent"], 100))
    from PIL import Image as _I
    img = _I.alpha_composite(img, glow_layer((W, H), _orb, 110))
    d = ImageDraw.Draw(img)

    text(d, (96, 34), "“", 200, PAL["accent"], True, "la")
    l1 = "换手机的理由只有一个：体验真的变好了，"
    l2 = "而不是参数表上多了一行「AI」。"
    assert tw(d, l1, 48, True) < W - 200 and tw(d, l2, 48, True) < W - 200
    text(d, (W / 2, 220), l1, 48, PAL["text"], True, "mm")
    text(d, (W / 2, 305), l2, 48, PAL["text"], True, "mm")
    text(d, (W / 2, 400), "—— 为体验买单，不为概念买单", 26, PAL["muted"], False, "mm")
    save(img, OUT / "fig3-quote.png")

if __name__ == "__main__":
    cover(); fig1(); fig2(); fig3()

#!/usr/bin/env python3
"""Render cover + in-article figures for 2026-09-20 正视淘汰机制 (run from repo root)."""
import math
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "tools"))
from figure_kit import (PAL, card, dot_grid, glow_layer, gradient, rgba,
                        save, text, tw)

OUT = pathlib.Path(__file__).parent

# ---------- cover: ascending steps with a fading block ----------
def cover():
    from PIL import Image, ImageDraw
    W, H = 1800, 766
    img = gradient((W, H), PAL["bg1"], "#2a3fb0")
    img = dot_grid(img)

    d = ImageDraw.Draw(img)
    # four ascending steps along the bottom
    steps = [(360, 260), (640, 380), (920, 500), (1200, 620)]  # (x, top y)
    sw, gap = 250, 10
    for x, ty in steps:
        d.rounded_rectangle([x, ty, x + sw, H], radius=18,
                            fill=rgba("#131c46"), outline=rgba("#2c3a7a"),
                            width=3)
    # blocks on top of steps (square people)
    def block(x, y, s, alpha=255, fill="#a8bcff"):
        d.rounded_rectangle([x - s / 2, y - s, x + s / 2, y], radius=12,
                            fill=rgba(fill, alpha), outline=rgba("#e8eeff", alpha),
                            width=3)

    block(485, steps[0][1], 86, 235)
    block(765, steps[1][1], 86, 255)
    block(1045, steps[2][1], 86, 255)
    # top block glows
    def _glow(dr):
        dr.rounded_rectangle([1290 - 60, steps[3][1] - 120, 1350 + 60, steps[3][1] + 20],
                             radius=28, fill=rgba("#7c9cff", 170))
    img = Image.alpha_composite(img, glow_layer((W, H), _glow, 34))
    d = ImageDraw.Draw(img)
    block(1325, steps[3][1], 92, 255, "#d3ddff")
    # the faded, stepped-off block beside the lowest step
    block(300, H - 26, 74, 90, "#8a93c9")
    # dashed trail from lowest step to the faded block
    for dx in range(20):
        d.line([300 + dx * 14 + 6, H - 130 + (dx % 2) * 0, 300 + dx * 14 + 14, H - 130],
               fill=rgba("#5f7dff", 60), width=3)

    save(img, OUT / "cover.png")

# ---------- fig 1: GE vitality curve 20-70-10 ----------
def fig1():
    from PIL import Image, ImageDraw
    W, H = 1600, 920
    img = gradient((W, H), PAL["bg1"], "#1a2455")
    img = dot_grid(img)
    d = ImageDraw.Draw(img)

    text(d, (W / 2, 74), "GE 活力曲线：20-70-10", 52, PAL["text"], True, "mm")
    text(d, (W / 2, 144), "杰克·韦尔奇时代 GE 的绩效分配框架", 26, "#aab4e6", False, "mm")

    x0, x1, ybase, ytop = 150, 1450, 660, 250
    def px(x):  # map x in [-3, 3]
        return x0 + (x + 3) / 6 * (x1 - x0)
    def py(v):  # v = exp(-x^2) in (0, 1]
        return ybase - v * (ybase - ytop)

    splits = (-0.595, 0.906)  # 20% / 90% quantiles of the curve
    zones = [
        (-3.0, splits[0], "#3b5bfd", 200, "A 类 · 前 20%", "重点奖励与培养"),
        (splits[0], splits[1], "#22346f", 230, "B 类 · 70%", "组织主体"),
        (splits[1], 3.0, "#2b2036", 250, "C 类 · 后 10%", "淘汰退出"),
    ]
    N = 90
    for xa, xb, color, alpha, _, _ in zones:
        pts = [(px(xa), ybase)]
        for i in range(N + 1):
            x = xa + (xb - xa) * i / N
            pts.append((px(x), py(math.exp(-x * x))))
        pts.append((px(xb), ybase))
        d.polygon(pts, fill=rgba(color, alpha), outline=rgba("#8fa3f0", 90))

    # curve stroke on top
    pts = [(px(-3 + 6 * i / 240), py(math.exp(-(-3 + 6 * i / 240) ** 2)))
           for i in range(241)]
    d.line(pts, fill=rgba("#a8bcff"), width=5, joint="curve")
    d.line([x0 - 10, ybase, x1 + 10, ybase], fill=rgba("#3d4f9e"), width=3)

    # dashed vertical dividers at the two split points
    for xs, div_color in ((splits[0], "#4c63d8"), (splits[1], "#c98a8a")):
        cx = px(xs)
        cy = py(math.exp(-xs * xs))
        for k in range(26):
            y_a = ybase - k * (ybase - cy) / 26
            y_b = ybase - (k + 0.5) * (ybase - cy) / 26
            d.line([cx, y_a, cx, y_b], fill=rgba(div_color, 190), width=3)

    labels = [(px(-3) + (px(splits[0]) - px(-3)) / 2, "A 类 · 前 20%", "重点奖励与培养", PAL["bright"]),
              (px(splits[0]) + (px(splits[1]) - px(splits[0])) / 2, "B 类 · 70%", "组织主体", PAL["text"]),
              (px(splits[1]) + (px(3) - px(splits[1])) / 2, "C 类 · 后 10%", "淘汰退出", "#d9a0a0")]
    for cx, t1, t2, c in labels:
        assert tw(d, t1, 30, True) < (x1 - x0) / 2, t1
        text(d, (cx, ybase + 78), t1, 30, c, True, "mm")
        text(d, (cx, ybase + 130), t2, 24, "#aab4e6", False, "mm")

    text(d, (W / 2, 856), "横轴：绩效表现（左高右低）", 24, PAL["muted"], False, "mm")
    save(img, OUT / "fig1-vitality-curve.png")

# ---------- fig 2: weapon vs mechanism (light) ----------
def fig2():
    from PIL import Image, ImageDraw
    W, H = 1600, 880
    img = gradient((W, H), "#eef1fb", "#f8faff")
    d = ImageDraw.Draw(img)
    text(d, (W / 2, 68), "同一个机制，两种命运", 52, PAL["light_text"], True, "mm")

    cw, ch, y = 660, 640, 150
    lx, rx = 110, W - 110 - cw

    left_items = ["标准模糊，年底突然宣判", "排名变成内部政治", "退出仓促，毫无尊严"]
    right_items = ["规则前置，入职即知", "反馈持续，没有惊吓", "出口体面，转岗有补偿"]

    # left: weapon (gray)
    card(d, [lx, y, lx + cw, y + ch], radius=24, fill="#eceef4",
         outline="#d5d9e4")
    d.ellipse([lx + cw / 2 - 36, y + 36, lx + cw / 2 + 36, y + 108],
              fill=rgba("#8a8f99"))
    text(d, (lx + cw / 2, y + 72), "✕", 40, "#ffffff", True, "mm")
    text(d, (lx + cw / 2, y + 152), "把淘汰当武器", 40, PAL["light_text"], True, "mm")
    for i, s in enumerate(left_items):
        text(d, (lx + 70, y + 236 + i * 62), "· " + s, 30, "#5f6470", False, "lm")
    d.line([lx + 60, y + 440, lx + cw - 60, y + 440], fill=rgba("#d5d9e4"), width=2)
    text(d, (lx + cw / 2, y + 500), "结果：内耗、互防", 30, "#8a8f99", True, "mm")
    text(d, (lx + cw / 2, y + 552), "劣币驱逐良币", 30, "#8a8f99", True, "mm")

    # right: mechanism (accent)
    card(d, [rx, y, rx + cw, y + ch], radius=24, fill=PAL["light_card"],
         outline="#b9c6ff")
    d.ellipse([rx + cw / 2 - 36, y + 36, rx + cw / 2 + 36, y + 108],
              fill=rgba(PAL["accent"]))
    text(d, (rx + cw / 2, y + 72), "✓", 40, "#ffffff", True, "mm")
    text(d, (rx + cw / 2, y + 152), "把淘汰当机制", 40, PAL["light_text"], True, "mm")
    for i, s in enumerate(right_items):
        assert tw(d, "· " + s, 30) < cw - 100, s
        text(d, (rx + 70, y + 236 + i * 62), "· " + s, 30, "#3f4450", False, "lm")
    d.line([rx + 60, y + 440, rx + cw - 60, y + 440], fill=rgba("#b9c6ff"), width=2)
    text(d, (rx + cw / 2, y + 500), "结果：流动、活力", 30, PAL["accent"], True, "mm")
    text(d, (rx + cw / 2, y + 552), "留住人心", 30, PAL["accent"], True, "mm")

    save(img, OUT / "fig2-two-ways.png")

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
    l1 = "员工不怕规则严，怕的是规则糊。"
    assert tw(d, l1, 54, True) < W - 200
    text(d, (W / 2, 230), l1, 54, PAL["text"], True, "mm")
    sub = "—— 装作没有淘汰的公司，往往在用最差的方式淘汰人"
    assert tw(d, sub, 26) < W - 200
    text(d, (W / 2, 350), sub, 26, PAL["muted"], False, "mm")
    save(img, OUT / "fig3-quote.png")

if __name__ == "__main__":
    cover(); fig1(); fig2(); fig3()

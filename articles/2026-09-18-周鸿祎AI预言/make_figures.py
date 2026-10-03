#!/usr/bin/env python3
"""Render cover + in-article figures for 2026-09-18 周鸿祎AI预言 (run from repo root)."""
import math
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "tools"))
from figure_kit import (PAL, card, dot_grid, glow_layer, gradient, rgba,
                        save, text, tw)

OUT = pathlib.Path(__file__).parent

# ---------- cover: agent-network motif, no text ----------
def cover():
    from PIL import Image, ImageDraw
    W, H = 1800, 766
    img = gradient((W, H), PAL["bg1"], "#2a3fb0")
    img = dot_grid(img)

    hubs = [(1230, 290), (590, 470), (930, 170)]
    nodes = [(240, 160), (420, 120), (660, 210), (820, 360), (300, 400),
             (470, 560), (700, 620), (990, 520), (1150, 620), (1380, 470),
             (1500, 300), (1400, 150), (1120, 90), (760, 60), (170, 620),
             (1080, 250), (1300, 380), (540, 330), (1620, 560), (900, 640)]
    sizes = [7, 9, 6, 8, 7, 10, 8, 9, 7, 11, 8, 6, 9, 7, 8, 6, 10, 7, 9, 8]

    def _glow(dr):
        for hx, hy in hubs:
            dr.ellipse([hx - 70, hy - 70, hx + 70, hy + 70],
                       fill=rgba("#7c9cff", 130))
    img = Image.alpha_composite(img, glow_layer((W, H), _glow, 60))

    d = ImageDraw.Draw(img)
    # edges: node -> nearest hub, plus a few hub-hub links
    for x, y in nodes:
        hx, hy = min(hubs, key=lambda h: (h[0] - x) ** 2 + (h[1] - y) ** 2)
        d.line([x, y, hx, hy], fill=rgba("#5f7dff", 70), width=2)
    for i in range(len(hubs) - 1):
        d.line([hubs[i][0], hubs[i][1], hubs[i + 1][0], hubs[i + 1][1]],
               fill=rgba("#5f7dff", 50), width=2)
    # satellites
    for (x, y), r in zip(nodes, sizes):
        d.ellipse([x - r, y - r, x + r, y + r], fill=rgba("#a8bcff", 220))
    # hubs: ring + bright core
    for hx, hy in hubs:
        d.ellipse([hx - 26, hy - 26, hx + 26, hy + 26],
                  outline=rgba("#a8bcff", 200), width=4)
        d.ellipse([hx - 11, hy - 11, hx + 11, hy + 11], fill=rgba("#eaf0ff"))

    save(img, OUT / "cover.png")

# ---------- fig 1: three-year timeline (dark) ----------
def fig1():
    from PIL import Image, ImageDraw
    W, H = 1600, 640
    img = gradient((W, H), PAL["bg1"], "#1a2455")
    img = dot_grid(img)
    d = ImageDraw.Draw(img)

    text(d, (W / 2, 78), "从大模型到百亿智能体", 52, PAL["text"], True, "mm")
    text(d, (W / 2, 146), "周鸿祎 2026 年 AI 全景预测的分期逻辑", 26, PAL["muted"], False, "mm")

    ly = 420
    d.line([150, ly, 1420, ly], fill=rgba("#3d4f9e"), width=4)
    # arrow head
    d.polygon([(1420, ly - 16), (1456, ly), (1420, ly + 16)], fill=rgba("#3d4f9e"))

    miles = [
        (330, "2024", "大模型之年", "拼参数、比谁更聪明", False),
        (800, "2025", "智能体之年", "走出聊天框，开始执行任务", False),
        (1270, "2026", "百亿智能体之年", "全面融入经济循环", True),
    ]
    def _glow(dr):
        dr.ellipse([1270 - 56, ly - 56, 1270 + 56, ly + 56], fill=rgba(PAL["accent"], 170))
    img = Image.alpha_composite(img, glow_layer((W, H), _glow, 26))
    d = ImageDraw.Draw(img)

    for x, year, label, sub, hot in miles:
        r = 22 if hot else 15
        d.ellipse([x - r, ly - r, x + r, ly + r],
                  fill=rgba(PAL["bright"] if hot else PAL["accent"]),
                  outline=rgba("#eaf0ff", 255), width=3)
        text(d, (x, ly - 88), year, 46 if hot else 40, PAL["bright"], True, "mm")
        assert tw(d, label, 36, True) < 460, label
        text(d, (x, ly + 78), label, 36, PAL["text"], True, "mm")
        assert tw(d, sub, 24) < 460, sub
        text(d, (x, ly + 128), sub, 24, PAL["muted"], False, "mm")

    text(d, (W / 2, 600), "竞争焦点：从「比拼模型参数」转向「比拼落地」", 26, PAL["muted"], False, "mm")
    save(img, OUT / "fig1-timeline.png")

# ---------- fig 2: three cards for ordinary people (light) ----------
def fig2():
    from PIL import Image, ImageDraw
    W, H = 1600, 620
    img = gradient((W, H), "#eef1fb", "#f8faff")
    d = ImageDraw.Draw(img)
    text(d, (W / 2, 66), "普通人最该关注的三条", 52, PAL["light_text"], True, "mm")

    cards = [
        ("01", "服务新入口", "智能体取代 APP", "对话即服务"),
        ("02", "第二大脑", "AI 长期记忆成熟", "成为你的数字孪生"),
        ("03", "超级个体", "一人 + 一队智能体", "干出一个团队的产出"),
    ]
    cw, ch, gap, y = 440, 420, 40, 140
    for i, (num, title, l1, l2) in enumerate(cards):
        x = 100 + i * (cw + gap)
        card(d, [x, y, x + cw, y + ch], radius=24, fill=PAL["light_card"],
             outline=PAL["light_border"])
        cx = x + cw / 2
        d.ellipse([cx - 40, y + 56, cx + 40, y + 136], fill=rgba(PAL["accent"]))
        text(d, (cx, y + 96), num, 36, "#ffffff", True, "mm")
        assert tw(d, title, 40, True) < cw - 40, title
        text(d, (cx, y + 186), title, 40, PAL["light_text"], True, "mm")
        assert tw(d, l1, 28) < cw - 36, l1
        assert tw(d, l2, 28) < cw - 36, l2
        text(d, (cx, y + 258), l1, 28, PAL["light_muted"], False, "mm")
        text(d, (cx, y + 306), l2, 28, PAL["light_muted"], False, "mm")

    save(img, OUT / "fig2-cards.png")

# ---------- fig 3: quote card (dark) ----------
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
    l1 = "未来的差距，不在人与 AI 之间，"
    l2 = "而在会用智能体的人与不会用的人之间。"
    assert tw(d, l1, 50, True) < W - 200 and tw(d, l2, 50, True) < W - 200
    text(d, (W / 2, 220), l1, 50, PAL["text"], True, "mm")
    text(d, (W / 2, 310), l2, 50, PAL["text"], True, "mm")
    text(d, (W / 2, 400), "—— 预言的价值，是逼我们提前想好自己的位置", 26, PAL["muted"], False, "mm")
    save(img, OUT / "fig3-quote.png")

if __name__ == "__main__":
    cover(); fig1(); fig2(); fig3()

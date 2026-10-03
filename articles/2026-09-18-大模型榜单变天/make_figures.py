#!/usr/bin/env python3
"""Render in-article figures for 2026-09-18 大模型榜单变天 (run from repo root)."""
import sys, pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "tools"))
from figure_kit import (PAL, card, dot_grid, font, glow_layer, gradient, rgba,
                        save, text, tw)

OUT = pathlib.Path(__file__).parent

# ---------- fig 1: top-10 leaderboard structure (dark) ----------
def fig1():
    from PIL import Image, ImageDraw
    W, H = 1600, 1010
    img = gradient((W, H), PAL["bg1"], "#1a2455")
    img = dot_grid(img)
    d = ImageDraw.Draw(img)

    text(d, (W / 2, 80), "主流大模型榜单 · 前十格局", 52, PAL["text"], True, "mm")
    text(d, (W / 2, 150), "2026 年 9 月 · 据公开报道整理", 28, PAL["muted"], False, "mm")

    known = {1: ("Muse Spark 1.3 · Meta", "新榜首"),
             6: ("Kimi K3 · 月之暗面", "国产"),
             8: ("GLM-5.3 · 智谱", "国产")}
    x0, row_h, gap, y = 110, 62, 16, 210
    inner = W - 2 * x0

    # glow under highlighted rows
    def _glow(dr):
        for rank in known:
            ry = y + (rank - 1) * (row_h + gap)
            dr.rounded_rectangle([x0, ry, x0 + inner, ry + row_h], radius=18,
                                 fill=rgba(PAL["accent"], 90))
    img = Image.alpha_composite(img, glow_layer((W, H), _glow, 22))
    d = ImageDraw.Draw(img)

    for rank in range(1, 11):
        ry = y + (rank - 1) * (row_h + gap)
        hot = rank in known
        card(d, [x0, ry, x0 + inner, ry + row_h], radius=18,
             fill=PAL["card_hi"] if hot else PAL["card"],
             outline=PAL["border_hi"] if hot else PAL["border"])
        cy = ry + row_h / 2
        # rank badge
        bx = x0 + 42
        d.ellipse([bx - 19, cy - 19, bx + 19, cy + 19],
                  fill=rgba(PAL["accent"] if hot else "#222c63"),
                  outline=rgba("#4a5aa0" if not hot else PAL["accent"]), width=2)
        text(d, (bx, cy), str(rank), 24, "#ffffff" if hot else "#aab4e6", True, "mm")
        # name + right tag
        name_x, tag_x = x0 + 84, x0 + inner - 26
        if hot:
            name, tag = known[rank]
            assert tw(d, name, 34, True) + tw(d, tag, 26) + 140 < inner, name
            text(d, (name_x, cy), name, 34, PAL["text"], True, "lm")
            text(d, (tag_x, cy), tag, 26, PAL["bright"], True, "rm")
        else:
            text(d, (name_x, cy), "海外模型", 30, "#aab4e6", False, "lm")

    save(img, OUT / "fig1-ranking.png")

# ---------- fig 2: three main lines (light cards) ----------
def fig2():
    from PIL import Image, ImageDraw
    W, H = 1600, 620
    img = gradient((W, H), "#eef1fb", "#f8faff")
    d = ImageDraw.Draw(img)
    text(d, (W / 2, 66), "2026 年的三条主线", 52, PAL["light_text"], True, "mm")

    cards = [
        ("01", "智能体主战场", "从「会聊天」到「会办事」", "多步骤任务成考核核心"),
        ("02", "端侧破局", "顶尖模型装进手机", "AI 手机从卖点变标配"),
        ("03", "算力打底", "国产 GPU 建设加速", "有卡者才有入场券"),
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

    save(img, OUT / "fig2-pillars.png")

# ---------- fig 3: quote card (dark) ----------
def fig3():
    from PIL import Image, ImageDraw
    W, H = 1600, 540
    img = gradient((W, H), PAL["bg1"], "#233299")
    img = dot_grid(img)

    def _orb(dr):
        dr.ellipse([W - 420, -200, W + 200, 340], fill=rgba("#7c9cff", 90))
        dr.ellipse([-260, H - 260, 300, H + 200], fill=rgba(PAL["accent"], 100))
    from PIL import Image as _I
    img = _I.alpha_composite(img, glow_layer((W, H), _orb, 110))
    d = ImageDraw.Draw(img)

    text(d, (96, 34), "“", 200, PAL["accent"], True, "la")
    q = "模型越卷，工具越便宜好用。"
    d0 = ImageDraw.Draw(img)
    assert tw(d0, q, 56, True) < W - 200, q
    text(d, (W / 2, 225), q, 56, PAL["text"], True, "mm")
    sub = "与其纠结哪个最强，不如把 AI 用进自己的工作流"
    assert tw(d0, sub, 28) < W - 200, sub
    text(d, (W / 2, 330), sub, 28, PAL["muted"], False, "mm")
    save(img, OUT / "fig3-quote.png")

if __name__ == "__main__":
    fig1(); fig2(); fig3()

#!/usr/bin/env python3
"""Render in-article figures for 2026-09-21 GPT-6 Astra 发布 (run from repo root)."""
import sys, pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "tools"))
from figure_kit import (PAL, card, dot_grid, glow_layer, gradient, rgba,
                        save, text, tw)

OUT = pathlib.Path(__file__).parent

# ---------- fig 1: key stats grid (dark) ----------
def fig1():
    from PIL import Image, ImageDraw
    W, H = 1600, 940
    img = gradient((W, H), PAL["bg1"], "#1a2455")
    img = dot_grid(img)
    d = ImageDraw.Draw(img)

    text(d, (W / 2, 78), "GPT-6 Astra · 关键数据速览", 52, PAL["text"], True, "mm")
    text(d, (W / 2, 148), "2026 年 9 月 3 日发布 · 据公开报道整理", 28, PAL["muted"], False, "mm")

    stats = [
        ("10万+", "训练用 GPU", "得州 Stargate 数据中心"),
        ("105万", "上下文窗口（token）", "最大输出 12.8 万 token"),
        ("72.6分", "OSWorld 2.0 桌面操作", "上一代 GPT-5.6 为 65.7"),
        ("4倍", "金融建模速度", "对比人类冠军级选手"),
        ("40分钟", "单任务平均耗时", "点软件·填表·跑流程全自动"),
        ("$10/$50", "每百万 token 定价", "输入 / 输出"),
    ]
    cw, ch, gap, x0, y0 = 440, 300, 40, 100, 210
    for i, (val, label, sub) in enumerate(stats):
        cx0 = x0 + (i % 3) * (cw + gap)
        cy0 = y0 + (i // 3) * (ch + gap)
        hot = i == 2  # OSWorld score is the headline number
        card(d, [cx0, cy0, cx0 + cw, cy0 + ch], radius=24,
             fill=PAL["card_hi"] if hot else PAL["card"],
             outline=PAL["border_hi"] if hot else PAL["border"])
        ccx = cx0 + cw / 2
        assert tw(d, val, 60, True) < cw - 48, val
        text(d, (ccx, cy0 + 96), val, 60, PAL["bright"] if hot else PAL["text"], True, "mm")
        assert tw(d, label, 30, True) < cw - 40, label
        text(d, (ccx, cy0 + 180), label, 30, PAL["text"], True, "mm")
        assert tw(d, sub, 24) < cw - 36, sub
        text(d, (ccx, cy0 + 234), sub, 24, PAL["muted"], False, "mm")

    save(img, OUT / "fig1-stats.png")

# ---------- fig 2: three battlegrounds (light cards) ----------
def fig2():
    from PIL import Image, ImageDraw
    W, H = 1600, 620
    img = gradient((W, H), "#eef1fb", "#f8faff")
    d = ImageDraw.Draw(img)
    text(d, (W / 2, 66), "它强在哪：三大主战场", 52, PAL["light_text"], True, "mm")

    cards = [
        ("01", "操作电脑", "OSWorld 2.0 拿下 72.6 分", "40 分钟任务全程无人接管"),
        ("02", "工程与建模", "电路原理图直接转 PCB", "金融建模 4 倍人类冠军"),
        ("03", "网络安全", "攻防能力大幅跃升", "受限开放 · 用前需申请"),
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

    save(img, OUT / "fig2-strengths.png")

# ---------- fig 3: release-week timeline (light) ----------
def fig3():
    from PIL import Image, ImageDraw
    W, H = 1600, 700
    img = gradient((W, H), "#eef1fb", "#f8faff")
    d = ImageDraw.Draw(img)
    text(d, (W / 2, 66), "72 小时 · 超级发布周", 52, PAL["light_text"], True, "mm")

    events = [
        ("9月1日", "Anthropic", "Fable 5.1 + Mythos 5.1", "双模型齐发"),
        ("9月2日", "Google", "Gemini 3.8 Flash", "六周内第三款 Flash"),
        ("9月2日", "Meta", "Muse Spark 1.3", "三天后登顶 30 模型榜"),
        ("9月3日", "OpenAI", "GPT-6 Astra", "「AGI 时代」宣言"),
    ]
    cw, ch, gap, x0 = 340, 300, 40, 80
    line_y, y_card = 250, 300
    d.line([x0 + cw / 2 - 60, line_y, x0 + 3 * (cw + gap) + cw / 2 + 60, line_y],
           fill=rgba("#c3cdf2"), width=4)

    for i, (date, org, model, note) in enumerate(events):
        x = x0 + i * (cw + gap)
        cx = x + cw / 2
        last = i == 3
        # date above the line
        assert tw(d, date, 28, True) < cw - 20, date
        text(d, (cx, line_y - 58), date, 28, PAL["light_text"], True, "mm")
        # node on the line
        d.ellipse([cx - 14, line_y - 14, cx + 14, line_y + 14],
                  fill=rgba(PAL["accent"] if last else "#ffffff"),
                  outline=rgba(PAL["accent"]), width=4)
        # card
        card(d, [x, y_card, x + cw, y_card + ch], radius=22,
             fill=PAL["light_card"],
             outline=PAL["accent"] if last else PAL["light_border"],
             width=3 if last else 2)
        assert tw(d, org, 36, True) < cw - 36, org
        text(d, (cx, y_card + 66), org, 36, PAL["light_text"], True, "mm")
        assert tw(d, model, 26, True) < cw - 32, model
        text(d, (cx, y_card + 140), model, 26, PAL["accent"], True, "mm")
        assert tw(d, note, 24) < cw - 28, note
        text(d, (cx, y_card + 208), note, 24, PAL["light_muted"], False, "mm")
        if last:
            bw = tw(d, "压轴", 22, True) + 36
            d.rounded_rectangle([cx - bw / 2, y_card + 248, cx + bw / 2, y_card + 282],
                                radius=14, fill=rgba(PAL["accent"]))
            text(d, (cx, y_card + 265), "压轴", 22, "#ffffff", True, "mm")

    save(img, OUT / "fig3-timeline.png")

# ---------- fig 4: quote card (dark) ----------
def fig4():
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
    q = "模型按周迭代，用法不能一成不变。"
    d0 = ImageDraw.Draw(img)
    assert tw(d0, q, 56, True) < W - 200, q
    text(d, (W / 2, 225), q, 56, PAL["text"], True, "mm")
    sub = "别追每一个新模型，让 AI 替你完整干一次活"
    assert tw(d0, sub, 28) < W - 200, sub
    text(d, (W / 2, 330), sub, 28, PAL["muted"], False, "mm")
    save(img, OUT / "fig4-quote.png")

if __name__ == "__main__":
    fig1(); fig2(); fig3(); fig4()

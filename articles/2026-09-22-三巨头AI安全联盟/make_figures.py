#!/usr/bin/env python3
"""Render in-article figures for 2026-09-22 三巨头 AI 安全联盟 (run from repo root)."""
import sys, pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "tools"))
from figure_kit import (PAL, card, dot_grid, glow_layer, gradient, rgba,
                        save, text, tw)

OUT = pathlib.Path(__file__).parent

# ---------- fig 1: 2026 timeline (dark) ----------
def fig1():
    from PIL import Image, ImageDraw
    W, H = 1600, 760
    img = gradient((W, H), PAL["bg1"], "#1a2455")
    img = dot_grid(img)
    d = ImageDraw.Draw(img)

    text(d, (W / 2, 70), "2026 · AI 安全大事记", 52, PAL["text"], True, "mm")
    text(d, (W / 2, 138), "从政府出手，到三巨头自己谈 · 据公开报道整理", 28, PAL["muted"], False, "mm")

    events = [
        ("2月28日", "政府翻脸", "Anthropic 遭联邦停用", "安全分歧公开化"),
        ("8月3日", "白宫召集", "四巨头谈自愿框架", "不强制 · 不成法"),
        ("9月13日", "媒体爆料", "密谈「标准组织」", "The Information 独家"),
        ("9月中旬", "官方确认", "OpenAI：已谈数周", "「不需反垄断豁免」"),
        ("9月19日", "对簿公堂", "「慢下来协议」被诉", "4 名付费用户发起"),
    ]
    cw, ch, gap = 272, 270, 30
    x0 = (W - (5 * cw + 4 * gap)) / 2
    line_y, y_card = 250, 300
    d.line([x0 + cw / 2 - 40, line_y, x0 + 4 * (cw + gap) + cw / 2 + 40, line_y],
           fill=rgba("#3a4a8f"), width=4)

    for i, (date, title, l1, l2) in enumerate(events):
        x = x0 + i * (cw + gap)
        cx = x + cw / 2
        hot = i == 2  # the scoop that started this story
        assert tw(d, date, 28, True) < cw - 20, date
        text(d, (cx, line_y - 52), date, 28, PAL["bright"] if hot else PAL["text"], True, "mm")
        d.ellipse([cx - 14, line_y - 14, cx + 14, line_y + 14],
                  fill=rgba(PAL["accent"] if hot else "#0a0e23"),
                  outline=rgba("#7c9cff" if hot else PAL["accent"]), width=4)
        card(d, [x, y_card, x + cw, y_card + ch], radius=22,
             fill=PAL["card_hi"] if hot else PAL["card"],
             outline=PAL["border_hi"] if hot else PAL["border"],
             width=3 if hot else 2)
        assert tw(d, title, 32, True) < cw - 28, title
        text(d, (cx, y_card + 70), title, 32, PAL["text"], True, "mm")
        assert tw(d, l1, 23) < cw - 28, l1
        text(d, (cx, y_card + 152), l1, 23, PAL["bright"] if hot else PAL["text"], False, "mm")
        assert tw(d, l2, 22) < cw - 28, l2
        text(d, (cx, y_card + 208), l2, 22, PAL["muted"], False, "mm")

    save(img, OUT / "fig1-timeline.png")

# ---------- fig 2: why now (light cards) ----------
def fig2():
    from PIL import Image, ImageDraw
    W, H = 1600, 620
    img = gradient((W, H), "#eef1fb", "#f8faff")
    d = ImageDraw.Draw(img)
    text(d, (W / 2, 66), "为什么是现在：政府退场了", 52, PAL["light_text"], True, "mm")

    cards = [
        ("01", "监管在退场", "自监管机构行政令搁浅", "白宫转向轻监管路线"),
        ("02", "政府翻过脸", "2月 Anthropic 遭联邦停用", "与大厂最狠的一次冲突"),
        ("03", "框架太软", "白宫只谈「自愿」测试", "不强制 · 不成法 · 没牙齿"),
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

    save(img, OUT / "fig2-why.png")

# ---------- fig 3: two voices (light comparison) ----------
def fig3():
    from PIL import Image, ImageDraw
    W, H = 1600, 780
    img = gradient((W, H), "#eef1fb", "#f8faff")
    d = ImageDraw.Draw(img)
    text(d, (W / 2, 66), "一边握手，一边被告：两种声音", 52, PAL["light_text"], True, "mm")

    cols = [
        ("乐观的一面", "行业补位", PAL["accent"], [
            "政府缺位，行业把责任接过来",
            "安全标准统一，测试结果互认",
            "出了事，响应有章可循",
        ]),
        ("担心的一面", "谁来监督", "#b54747", [
            "立规矩的，正是被管的人",
            "「慢下来协议」诉讼在途",
            "中小厂商和开源，可能进不了门",
        ]),
    ]
    cw, ch, gap = 700, 480, 60
    y = 150
    for i, (head, tag, color, items) in enumerate(cols):
        x = 70 + i * (cw + gap)
        card(d, [x, y, x + cw, y + ch], radius=26, fill=PAL["light_card"],
             outline=PAL["light_border"])
        # header pill (solid fill + white text: ImageDraw does no alpha
        # blending, a translucent tint would replace pixels and hide the text)
        pw = tw(d, head, 30, True) + 48
        d.rounded_rectangle([x + 40, y + 40, x + 40 + pw, y + 96], radius=28,
                            fill=rgba(color), outline=rgba(color), width=2)
        text(d, (x + 40 + pw / 2, y + 68), head, 30, "#ffffff", True, "mm")
        text(d, (x + 40 + pw + 24, y + 68), "· " + tag, 26, PAL["light_muted"], False, "lm")
        for j, it in enumerate(items):
            iy = y + 170 + j * 96
            d.ellipse([x + 48, iy - 9, x + 66, iy + 9], fill=rgba(color))
            assert tw(d, it, 26) < cw - 140, it
            text(d, (x + 88, iy), it, 26, PAL["light_text"], False, "lm")

    # VS badge on the seam
    vs = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    vd = ImageDraw.Draw(vs)
    vd.ellipse([W / 2 - 44, y + ch / 2 - 44, W / 2 + 44, y + ch / 2 + 44],
               fill=(255, 255, 255, 255), outline=rgba(PAL["accent"]), width=4)
    from figure_kit import font
    vd.text((W / 2, y + ch / 2), "VS", font=font(34, True), fill=rgba(PAL["accent"]), anchor="mm")
    img = Image.alpha_composite(img, vs)
    save(img, OUT / "fig3-two-voices.png")

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
    q = "政府退场之后，裁判权不会消失——只会换人。"
    d0 = ImageDraw.Draw(img)
    assert tw(d0, q, 56, True) < W - 200, q
    text(d, (W / 2, 225), q, 56, PAL["text"], True, "mm")
    sub = "这次握手，是行业的成人礼，还是巨头的新围墙？"
    assert tw(d0, sub, 28) < W - 200, sub
    text(d, (W / 2, 330), sub, 28, PAL["muted"], False, "mm")
    save(img, OUT / "fig4-quote.png")

if __name__ == "__main__":
    fig1(); fig2(); fig3(); fig4()

#!/usr/bin/env python3
"""Render cover + in-article figures for 2026-09-20 比破产更贵的是硬撑 (run from repo root)."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "tools"))
from figure_kit import (PAL, card, dot_grid, glow_layer, gradient, rgba,
                        save, text, tw)

OUT = pathlib.Path(__file__).parent

def _beat(x, y, w=180):
    """One ECG heartbeat starting at (x, y); returns list of points."""
    k = w / 180
    return [(x, y), (x + 30 * k, y - 10), (x + 46 * k, y),
            (x + 70 * k, y), (x + 82 * k, y + 10), (x + 94 * k, y - 110),
            (x + 108 * k, y + 40), (x + 118 * k, y), (x + 148 * k, y + 12),
            (x + 168 * k, y - 20), (x + w, y)]

# ---------- cover: ECG line that splits - survive vs fade out ----------
def cover():
    from PIL import Image, ImageDraw
    W, H = 1800, 766
    img = gradient((W, H), PAL["bg1"], "#2a3fb0")
    img = dot_grid(img)

    y0 = 420
    pts = [(180, y0)]
    x = 180
    for _ in range(4):
        pts += _beat(x, y0)[1:]
        x += 180
    # chaotic stretch
    for dx, dy in ((30, -70), (60, 60), (40, -90), (70, 70), (50, -60),
                   (60, 50), (40, -80)):
        x += dx
        pts.append((x, y0 + dy))
    split_x = x  # ~ 4*180+120+350 = ~1190

    alive = _beat(split_x, y0 - 110, 150) + _beat(split_x + 150, y0 - 110, 150)

    def _glow(dr):
        dr.line(pts, fill=rgba("#7c9cff", 150), width=10, joint="curve")
        dr.line(alive, fill=rgba("#7c9cff", 120), width=8, joint="curve")
    img = Image.alpha_composite(img, glow_layer((W, H), _glow, 18))

    d = ImageDraw.Draw(img)
    d.line(pts, fill=rgba("#a8bcff"), width=5, joint="curve")

    # upper branch: keeps beating (alive)
    d.line(alive, fill=rgba("#d3ddff"), width=5, joint="curve")

    # lower branch: flattens and fades
    fade = [(split_x, y0 + 130), (split_x + 80, y0 + 150),
            (split_x + 160, y0 + 158), (split_x + 250, y0 + 162),
            (split_x + 350, y0 + 164), (split_x + 450, y0 + 165)]
    assert fade[-1][0] < 1800 and split_x + 300 < 1800
    for i in range(len(fade) - 1):
        a = 150 - i * 32
        d.line([fade[i], fade[i + 1]], fill=rgba("#8a93c9", max(a, 25)), width=4)

    save(img, OUT / "cover.png")

# ---------- fig 1: three programs of bankruptcy law ----------
def fig1():
    from PIL import Image, ImageDraw
    W, H = 1600, 880
    img = gradient((W, H), PAL["bg1"], "#1a2455")
    img = dot_grid(img)
    d = ImageDraw.Draw(img)

    text(d, (W / 2, 74), "破产法的三种程序", 52, PAL["text"], True, "mm")
    text(d, (W / 2, 144), "进入程序，不等于终点", 26, "#aab4e6", False, "mm")

    # left node: distressed company
    nx, ny, nw, nh = 110, 330, 300, 230
    d.rounded_rectangle([nx, ny, nx + nw, ny + nh], radius=24,
                        fill=rgba("#131b3f"), outline=rgba("#4c63d8"), width=3)
    text(d, (nx + nw / 2, ny + 92), "企业陷入", 34, PAL["muted"], False, "mm")
    text(d, (nx + nw / 2, ny + 140), "债务困境", 34, PAL["muted"], False, "mm")

    progs = [
        (520, "重整", "救治", "调整债务 · 引入战投\n保留经营主体", True),
        (890, "和解", "协商", "与债权人会议\n达成减债缓债协议", False),
        (1260, "清算", "退出", "变价分配财产\n注销主体资格", False),
    ]
    pw, ph, py = 320, 400, 240
    for px, name, tag, desc, hot in progs:
        card(d, [px, py, px + pw, py + ph], radius=24,
             fill=PAL["card_hi"] if hot else PAL["card"],
             outline=PAL["border_hi"] if hot else PAL["border"])
        # connector from left node
        d.line([nx + nw, ny + nh / 2, px - 14, py + 90], fill=rgba("#4c63d8"), width=3)
        d.polygon([(px, py + 90), (px - 16, py + 82), (px - 16, py + 98)],
                  fill=rgba("#4c63d8"))
        text(d, (px + pw / 2, py + 72), name, 44, PAL["bright"], True, "mm")
        d.rounded_rectangle([px + pw / 2 - 46, py + 116, px + pw / 2 + 46, py + 156],
                            radius=20, fill=rgba(PAL["accent"] if hot else "#2c3a7a"))
        text(d, (px + pw / 2, py + 136), tag, 26, "#ffffff", True, "mm")
        for i, ln in enumerate(desc.split("\n")):
            assert tw(d, ln, 26) < pw - 40, ln
            text(d, (px + pw / 2, py + 220 + i * 46), ln, 26, "#aab4e6", False, "mm")

    text(d, (W / 2, 720), "及早进入程序，恰恰是保住经营价值的办法", 28, PAL["bright"], True, "mm")
    text(d, (W / 2, 790), "案例：通用汽车 40 天重整重生 · 北大方正合并重整 · 海航 7000 亿负债重整",
         24, PAL["muted"], False, "mm")
    save(img, OUT / "fig1-three-programs.png")

# ---------- fig 2: four signals (2x2) ----------
def fig2():
    from PIL import Image, ImageDraw
    W, H = 1600, 900
    img = gradient((W, H), PAL["bg1"], "#1a2455")
    img = dot_grid(img)
    d = ImageDraw.Draw(img)

    text(d, (W / 2, 74), "「救不活了」的四个信号", 52, PAL["text"], True, "mm")
    text(d, (W / 2, 144), "命中越多 · 持续越久，生还概率越低", 26, "#aab4e6", False, "mm")

    cells = [
        ("01", "现金流结构性为负", "不是回款慢，是模式不赚钱"),
        ("02", "融资链条断裂", "借新还旧走不通，现金撑不过一个周期"),
        ("03", "核心业务被替代", "技术迁移、需求消失，衰落不可逆"),
        ("04", "靠输血不靠造血", "卖资产、补贴、关联借款维持心跳"),
    ]
    cw, ch, gx, gy, y0 = 660, 280, 60, 50, 190
    for i, (num, title, sub) in enumerate(cells):
        x = 110 + (i % 2) * (cw + gx)
        y = y0 + (i // 2) * (ch + gy)
        card(d, [x, y, x + cw, y + ch], radius=24)
        text(d, (x + 46, y + 80), num, 56, PAL["accent"], True, "lm")
        assert tw(d, title, 34, True) < cw - 160, title
        text(d, (x + 160, y + 64), title, 34, PAL["text"], True, "lm")
        assert tw(d, sub, 26) < cw - 200, sub
        text(d, (x + 160, y + 126), sub, 26, "#aab4e6", False, "lm")

    save(img, OUT / "fig2-four-signals.png")

# ---------- fig 3: cyclical vs structural (light) ----------
def fig3():
    from PIL import Image, ImageDraw
    W, H = 1600, 880
    img = gradient((W, H), "#eef1fb", "#f8faff")
    d = ImageDraw.Draw(img)
    text(d, (W / 2, 68), "周期性困难 vs 结构性死亡", 52, PAL["light_text"], True, "mm")

    cw, ch, y = 660, 660, 150
    lx, rx = 110, W - 110 - cw

    left_items = ["主业仍有毛利，缺口来自节奏", "回款慢、季节波动、短期下行",
                  "输血能换来造血", "撑过周期，企业更强"]
    right_items = ["商业模式本身不成立", "市场已经迁移，等不来回暖",
                   "输血只够续命，不止损", "拖得越久，残值越少"]

    card(d, [lx, y, lx + cw, y + ch], radius=24, fill=PAL["light_card"],
         outline="#b9c6ff")
    d.ellipse([lx + cw / 2 - 36, y + 36, lx + cw / 2 + 36, y + 108],
              fill=rgba(PAL["accent"]))
    text(d, (lx + cw / 2, y + 72), "撑", 40, "#ffffff", True, "mm")
    text(d, (lx + cw / 2, y + 152), "周期性困难", 40, PAL["light_text"], True, "mm")
    for i, s in enumerate(left_items):
        text(d, (lx + 70, y + 236 + i * 58), "· " + s, 29, "#3f4450", False, "lm")
    d.line([lx + 60, y + 486, lx + cw - 60, y + 486], fill=rgba("#b9c6ff"), width=2)
    text(d, (lx + cw / 2, y + 546), "值得撑", 32, PAL["accent"], True, "mm")

    card(d, [rx, y, rx + cw, y + ch], radius=24, fill="#eceef4", outline="#d5d9e4")
    d.ellipse([rx + cw / 2 - 36, y + 36, rx + cw / 2 + 36, y + 108],
              fill=rgba("#8a8f99"))
    text(d, (rx + cw / 2, y + 72), "退", 40, "#ffffff", True, "mm")
    text(d, (rx + cw / 2, y + 152), "结构性死亡", 40, PAL["light_text"], True, "mm")
    for i, s in enumerate(right_items):
        text(d, (rx + 70, y + 236 + i * 58), "· " + s, 29, "#5f6470", False, "lm")
    d.line([rx + 60, y + 486, rx + cw - 60, y + 486], fill=rgba("#d5d9e4"), width=2)
    text(d, (rx + cw / 2, y + 546), "该体面退场", 32, "#8a8f99", True, "mm")

    save(img, OUT / "fig3-two-troubles.png")

# ---------- fig 4: quote card ----------
def fig4():
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
    l1 = "让该退场的体面退场，"
    l2 = "活下来的才能真的活好。"
    assert tw(d, l1, 54, True) < W - 200 and tw(d, l2, 54, True) < W - 200
    text(d, (W / 2, 220), l1, 54, PAL["text"], True, "mm")
    text(d, (W / 2, 305), l2, 54, PAL["text"], True, "mm")
    sub = "—— 检验标准只有一条：注资之后，它能靠自己活下去吗？"
    assert tw(d, sub, 26) < W - 200
    text(d, (W / 2, 400), sub, 26, PAL["muted"], False, "mm")
    save(img, OUT / "fig4-quote.png")

if __name__ == "__main__":
    cover(); fig1(); fig2(); fig3(); fig4()

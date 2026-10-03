#!/usr/bin/env python3
"""Markdown -> WeChat Official Account paste-ready HTML.

Usage: python tools/md2wechat.py articles/xxx/article.md [output.html]

All styles are inline (WeChat editor strips <style> blocks and classes).
Output opens in a browser; Ctrl+A / Ctrl+C then paste into the WeChat
article editor and formatting survives.
"""
import html
import pathlib
import re
import sys

# ---------- theme ----------
ACCENT = "#3b5bfd"        # primary accent
TITLE = "#1f2329"         # heading color
BODY = "#3f3f46"          # body text
MUTED = "#8a8f99"         # secondary text
CODE_BG = "#f4f5f7"
QUOTE_BG = "#f2f4ff"
FONT = "-apple-system,BlinkMacSystemFont,'Helvetica Neue','PingFang SC','Hiragino Sans GB','Microsoft YaHei',sans-serif"
MONO = "'SF Mono',Consolas,'Courier New',monospace"

def esc(s: str) -> str:
    return html.escape(s, quote=False)

# ---------- inline rendering ----------
CODE_TOKEN = re.compile(r"`([^`]+)`")
BOLD_TOKEN = re.compile(r"\*\*(.+?)\*\*")
ITAL_TOKEN = re.compile(r"(?<!\*)\*([^*]+)\*(?!\*)")
IMG_TOKEN = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
LINK_TOKEN = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")

def render_inline(text: str) -> str:
    """Escape + convert inline markdown to inline-styled HTML."""
    s = esc(text)
    # inline code (protect content from further styling)
    def _code(m):
        return (f'<code style="margin:0 2px;padding:2px 6px;border-radius:4px;'
                f'background:{CODE_BG};font-family:{MONO};font-size:13.5px;'
                f'color:#c7254e;">{m.group(1)}</code>')
    s = CODE_TOKEN.sub(_code, s)
    # images
    def _img(m):
        alt, src = m.group(1), m.group(2)
        return (f'<img src="{src}" alt="{alt}" style="display:block;width:100%;'
                f'margin:10px auto;border-radius:8px;"/>')
    s = IMG_TOKEN.sub(_img, s)
    # links: WeChat strips <a>, render as accent-colored text
    def _link(m):
        return f'<span style="color:{ACCENT};border-bottom:1px solid {ACCENT};">{m.group(1)}</span>'
    s = LINK_TOKEN.sub(_link, s)
    # bold
    s = BOLD_TOKEN.sub(
        rf'<strong style="color:{TITLE};font-weight:600;">\1</strong>', s)
    # italic
    s = ITAL_TOKEN.sub(r'<em style="font-style:italic;color:{TITLE};">\1</em>'.replace("{TITLE}", TITLE), s)
    return s

# ---------- block rendering ----------

def p(text: str) -> str:
    return (f'<p style="margin:16px 0;font-size:15.5px;line-height:1.9;'
            f'color:{BODY};letter-spacing:.4px;text-align:justify;">{render_inline(text)}</p>')

def h2(text: str) -> str:
    return (f'<section style="margin:30px 0 14px;padding-left:10px;'
            f'border-left:4px solid {ACCENT};font-size:17.5px;font-weight:600;'
            f'color:{TITLE};line-height:1.5;">{render_inline(text)}</section>')

def h3(text: str) -> str:
    return (f'<section style="margin:22px 0 10px;font-size:15.5px;font-weight:600;'
            f'color:{TITLE};">{render_inline(text)}</section>')

def blockquote(lines: list[str]) -> str:
    inner = "".join(p(ln) if ln else "<br/>" for ln in lines)
    inner = inner.replace('margin:16px 0;', 'margin:6px 0;')
    return (f'<section style="margin:18px 0;padding:12px 16px;background:{QUOTE_BG};'
            f'border-left:3px solid {ACCENT};border-radius:0 8px 8px 0;'
            f'color:{MUTED};">{inner}</section>')

def li(text: str, ordered: bool, idx: int) -> str:
    marker = f"{idx}. " if ordered else "•&nbsp;"
    return (f'<p style="margin:8px 0 8px 6px;font-size:15.5px;line-height:1.85;'
            f'color:{BODY};letter-spacing:.4px;">'
            f'<span style="color:{ACCENT};font-weight:600;">{marker}</span>'
            f'{render_inline(text)}</p>')

def code_block(code: str) -> str:
    return (f'<section style="margin:18px 0;padding:14px 16px;background:#282c34;'
            f'border-radius:8px;overflow-x:auto;">'
            f'<pre style="margin:0;white-space:pre-wrap;font-family:{MONO};'
            f'font-size:13px;line-height:1.7;color:#abb2bf;">{esc(code)}</pre></section>')

def hr() -> str:
    return f'<section style="margin:26px 0;border-top:1px dashed #d5d9e0;"></section>'

def caption(text: str) -> str:
    return (f'<p style="margin:-4px 0 24px;font-size:13px;color:{MUTED};'
            f'text-align:center;letter-spacing:.5px;">{render_inline(text)}</p>')

def table(rows: list[list[str]]) -> str:
    out = [f'<section style="margin:18px 0;overflow-x:auto;">',
           f'<table style="border-collapse:collapse;width:100%;font-size:14px;">']
    for i, row in enumerate(rows):
        tag = "th" if i == 0 else "td"
        bg = "#eef1ff" if i == 0 else "#ffffff"
        if i % 2 == 1 and i != 0:
            bg = "#fafbfc"
        cells = "".join(
            f'<{tag} style="border:1px solid #e4e7ee;padding:8px 12px;background:{bg};'
            f'color:{TITLE if i == 0 else BODY};text-align:center;">{render_inline(c)}</{tag}>'
            for c in row)
        out.append(f"<tr>{cells}</tr>")
    out.append("</table></section>")
    return "".join(out)

def title_block(text: str, meta: str | None) -> str:
    t = (f'<section style="margin:8px 0 6px;font-size:21px;font-weight:700;'
         f'color:{TITLE};line-height:1.45;text-align:center;">{render_inline(text)}</section>')
    m = (f'<section style="margin:0 0 24px;font-size:13px;color:{MUTED};'
         f'text-align:center;">{esc(meta)}</section>') if meta else ""
    return t + m

# ---------- parser ----------

def convert(md_text: str) -> str:
    lines = md_text.splitlines()
    out: list[str] = []
    i, n = 0, len(lines)
    first_h1_done = False

    while i < n:
        line = lines[i]

        # fenced code block
        if line.strip().startswith("```"):
            code_lines = []
            i += 1
            while i < n and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            i += 1  # skip closing fence
            out.append(code_block("\n".join(code_lines)))
            continue

        # table (header row + separator row)
        if "|" in line and i + 1 < n and re.match(r"^\s*\|?[\s:|-]+\|?\s*$", lines[i + 1]) and "-" in lines[i + 1]:
            rows: list[list[str]] = []
            while i < n and "|" in lines[i]:
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                rows.append(cells)
                i += 1
            if len(rows) >= 2 and set(rows[1][0]) <= set("-: "):
                rows.pop(1)  # drop separator row
            out.append(table(rows))
            continue

        # blank
        if not line.strip():
            i += 1
            continue

        # headings
        m = re.match(r"^(#{1,3})\s+(.*)", line)
        if m:
            level, text = len(m.group(1)), m.group(2).strip()
            if level == 1 and not first_h1_done:
                out.append(title_block(text, None))
                first_h1_done = True
            elif level == 2:
                out.append(h2(text))
            else:
                out.append(h3(text))
            i += 1
            continue

        # hr
        if re.match(r"^\s*(---+|\*\*\*+)\s*$", line):
            out.append(hr())
            i += 1
            continue

        # blockquote (collect consecutive > lines, keep blank-line splits)
        if line.lstrip().startswith(">"):
            q: list[str] = []
            while i < n and (lines[i].lstrip().startswith(">") or (not lines[i].strip() and q and not lines[i - 1].strip())):
                if lines[i].lstrip().startswith(">"):
                    q.append(re.sub(r"^\s*>\s?", "", lines[i]))
                else:
                    q.append("")
                i += 1
            out.append(blockquote(q))
            continue

        # ordered list
        m = re.match(r"^\s*\d+[.、]\s+(.*)", line)
        if m:
            idx = 1
            while i < n and re.match(r"^\s*\d+[.、]\s+", lines[i]):
                out.append(li(re.match(r"^\s*\d+[.、]\s+(.*)", lines[i]).group(1), True, idx))
                idx += 1
                i += 1
            continue

        # unordered list
        if re.match(r"^\s*[-*+]\s+", line):
            while i < n and re.match(r"^\s*[-*+]\s+", lines[i]):
                out.append(li(re.match(r"^\s*[-*+]\s+(.*)", lines[i]).group(1), False, 0))
                i += 1
            continue

        # figure caption line
        if line.lstrip().startswith("▲"):
            out.append(caption(line.strip()))
            i += 1
            continue

        # paragraph (merge soft-wrapped lines)
        para = [line.strip()]
        i += 1
        while i < n and lines[i].strip() and not re.match(
                r"^(#{1,3}\s|```|\s*>|\s*[-*+]\s|\s*\d+[.、]\s|\s*---+\s*$|▲|!\[)", lines[i]) and "|" not in lines[i]:
            para.append(lines[i].strip())
            i += 1
        out.append(p(" ".join(para)))

    body = "".join(out)
    return (
        '<!DOCTYPE html><html><head><meta charset="utf-8"/>'
        "<title>公众号排版预览</title></head>"
        f'<body style="margin:0;background:#eef0f4;">'
        f'<section style="max-width:677px;margin:20px auto;padding:32px 24px;'
        f'background:#ffffff;border-radius:12px;font-family:{FONT};">{body}</section>'
        "</body></html>"
    )

def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    src = pathlib.Path(sys.argv[1])
    dst = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else src.with_suffix(".html")
    html_text = convert(src.read_text(encoding="utf-8"))
    dst.write_text(html_text, encoding="utf-8")
    print(f"OK -> {dst}  ({len(html_text)} bytes)")

if __name__ == "__main__":
    main()

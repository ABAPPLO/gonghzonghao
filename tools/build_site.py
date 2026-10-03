#!/usr/bin/env python3
"""聚合 articles/ 下的全部文章，生成静态发布站点 -> site/。

用法:
  python tools/build_site.py              # 构建 site/
  python tools/build_site.py --serve      # 构建后本地预览 http://127.0.0.1:8740
  python tools/build_site.py --serve 9000 # 指定端口

站点配置见根目录 site.json（站名 / 简介 / 公众号二维码 / 部署域名等）。
site/ 为纯静态文件，可直接整体部署到 GitHub Pages、Vercel、对象存储或任意服务器。
"""
from __future__ import annotations

import html
import json
import pathlib
import re
import shutil
import sys
from datetime import datetime

ROOT = pathlib.Path(__file__).resolve().parent.parent
ARTICLES = ROOT / "articles"
OUT = ROOT / "site"

DEFAULT_CONFIG = {
    "name": "AI 前线观察",
    "slogan": "每天一条 AI 圈有价值的动态",
    "intro": "",
    "wechat_id": "",       # 公众号微信号，留空则不显示
    "qr_image": "",        # 二维码图片相对根目录路径，如 "assets/qr.png"，留空显示占位
    "base_url": "",        # 部署后的正式域名（不带末尾斜杠），用于 RSS / og:image 绝对地址
    "footer_note": "",
}

IMG_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}
FOLDER_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})-(.+)$")

# ---------- 工具 ----------

def esc(s: str, quote: bool = False) -> str:
    return html.escape(s, quote=quote)


def date_cn(d: datetime) -> str:
    return f"{d.year} 年 {d.month} 月 {d.day} 日"


def load_config() -> dict:
    cfg = dict(DEFAULT_CONFIG)
    f = ROOT / "site.json"
    if f.exists():
        cfg.update(json.loads(f.read_text(encoding="utf-8")))
    return cfg


# ---------- Markdown -> HTML（类名版，供网站用） ----------

CODE_TOKEN = re.compile(r"`([^`]+)`")
IMG_TOKEN = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
LINK_TOKEN = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
BOLD_TOKEN = re.compile(r"\*\*(.+?)\*\*")
ITAL_TOKEN = re.compile(r"(?<!\*)\*([^*]+)\*(?!\*)")
IMG_LINE = re.compile(r"^\s*!\[([^\]]*)\]\(([^)]+)\)\s*$")


def inline(text: str) -> str:
    s = esc(text)
    s = CODE_TOKEN.sub(r"<code>\1</code>", s)
    s = IMG_TOKEN.sub(
        lambda m: f'<img src="{esc(m.group(2), True)}" alt="{esc(m.group(1), True)}" loading="lazy"/>', s)
    s = LINK_TOKEN.sub(r'<a href="\2" target="_blank" rel="noopener">\1</a>', s)
    s = BOLD_TOKEN.sub(r"<strong>\1</strong>", s)
    s = ITAL_TOKEN.sub(r"<em>\1</em>", s)
    return s


def md_to_html(md_text: str, *, drop_first_h1: bool = True) -> str:
    """覆盖现有文章用到的 Markdown 语法；样式全部走 site.css 的类名。"""
    lines = md_text.splitlines()
    out: list[str] = []
    i, n = 0, len(lines)
    h1_seen = False
    sec = 0

    while i < n:
        line = lines[i]

        # 围栏代码块
        if line.strip().startswith("```"):
            code = []
            i += 1
            while i < n and not lines[i].strip().startswith("```"):
                code.append(lines[i])
                i += 1
            i += 1
            out.append(f'<pre><code>{esc(chr(10).join(code))}</code></pre>')
            continue

        # 表格（表头 + 分隔行）
        if "|" in line and i + 1 < n and re.match(r"^\s*\|?[\s:|-]+\|?\s*$", lines[i + 1]) and "-" in lines[i + 1]:
            rows: list[list[str]] = []
            while i < n and "|" in lines[i]:
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            if len(rows) >= 2 and set(rows[1][0]) <= set("-: "):
                rows.pop(1)
            out.append('<div class="table-wrap"><table>')
            for r, row in enumerate(rows):
                tag = "th" if r == 0 else "td"
                cells = "".join(f"<{tag}>{inline(c)}</{tag}>" for c in row)
                out.append(f"<tr>{cells}</tr>")
            out.append("</table></div>")
            continue

        # 空行
        if not line.strip():
            i += 1
            continue

        # 标题
        m = re.match(r"^(#{1,3})\s+(.*)", line)
        if m:
            level, text = len(m.group(1)), m.group(2).strip()
            if level == 1 and not h1_seen:
                h1_seen = True
                if drop_first_h1:
                    i += 1
                    continue
                out.append(f'<h1 class="post-title">{inline(text)}</h1>')
            elif level <= 2:
                sec += 1
                out.append(f'<h2 id="s{sec}">{inline(text)}</h2>')
            else:
                out.append(f"<h3>{inline(text)}</h3>")
            i += 1
            continue

        # 分隔线
        if re.match(r"^\s*(---+|\*\*\*+)\s*$", line):
            out.append('<hr class="sep"/>')
            i += 1
            continue

        # 整行图片 + 可选 ▲ 图注 -> figure
        m = IMG_LINE.match(line)
        if m:
            alt, src = m.group(1), m.group(2)
            i += 1
            cap = ""
            if i < n and lines[i].lstrip().startswith("▲"):
                cap = lines[i].strip()
                i += 1
            fig = (f'<figure><img src="{esc(src, True)}" alt="{esc(alt, True)}" loading="lazy"/>')
            if cap:
                fig += f"<figcaption>{inline(cap)}</figcaption>"
            out.append(fig + "</figure>")
            continue

        # 引用块
        if line.lstrip().startswith(">"):
            q: list[str] = []
            while i < n and (lines[i].lstrip().startswith(">")
                             or (not lines[i].strip() and q and not lines[i - 1].strip())):
                q.append(re.sub(r"^\s*>\s?", "", lines[i].lstrip()) if lines[i].lstrip().startswith(">") else "")
                i += 1
            inner = "".join(f"<p>{inline(ln)}</p>" if ln.strip() else "<br/>" for ln in q)
            out.append(f"<blockquote>{inner}</blockquote>")
            continue

        # 有序列表
        if re.match(r"^\s*\d+[.、]\s+", line):
            out.append("<ol>")
            while i < n and re.match(r"^\s*\d+[.、]\s+", lines[i]):
                out.append(f"<li>{inline(re.match(r'^\s*\d+[.、]\s+(.*)', lines[i]).group(1))}</li>")
                i += 1
            out.append("</ol>")
            continue

        # 无序列表
        if re.match(r"^\s*[-*+]\s+", line):
            out.append("<ul>")
            while i < n and re.match(r"^\s*[-*+]\s+", lines[i]):
                out.append(f"<li>{inline(re.match(r'^\s*[-*+]\s+(.*)', lines[i]).group(1))}</li>")
                i += 1
            out.append("</ul>")
            continue

        # 单独 ▲ 行（无图片跟随）
        if line.lstrip().startswith("▲"):
            out.append(f'<p class="cap">{inline(line.strip())}</p>')
            i += 1
            continue

        # 段落（合并软换行）
        para = [line.strip()]
        i += 1
        while i < n and lines[i].strip() and not re.match(
                r"^(#{1,3}\s|```|\s*>|\s*[-*+]\s|\s*\d+[.、]\s|\s*---+\s*$|▲|!\[)", lines[i]) and "|" not in lines[i]:
            para.append(lines[i].strip())
            i += 1
        out.append(f"<p>{inline(' '.join(para))}</p>")

    return "".join(out)


def strip_md(text: str) -> str:
    """去掉 Markdown 记号，取纯文本（用于摘要 / 字数统计 / 搜索索引）。"""
    t = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
    t = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", t)
    t = re.sub(r"[#>*`~\-|▲]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


# ---------- 文章收集 ----------

def collect_articles() -> list[dict]:
    posts = []
    if not ARTICLES.exists():
        return posts
    for folder in sorted(ARTICLES.iterdir()):
        md = folder / "article.md"
        m = FOLDER_RE.match(folder.name)
        if not folder.is_dir() or not md.exists() or not m:
            continue
        text = md.read_text(encoding="utf-8")
        lines = text.splitlines()

        title = folder.name[m.end(1) + 1:]
        for ln in lines[:5]:
            hm = re.match(r"^#\s+(.*)", ln.strip())
            if hm:
                title = hm.group(1).strip()
                break

        digest = ""
        for idx, ln in enumerate(lines):
            s = ln.strip()
            if (not s or re.match(r"^(#|```|\s*>|\s*[-*+]\s|\s*\d+[.、]\s|!\[|▲|\|)", s)
                    or re.match(r"^-{3,}$", s)):
                continue
            digest = strip_md(s)
            break
        digest = digest[:92] + ("…" if len(digest) > 92 else "")

        plain = strip_md(text)
        n_cjk = len(re.findall(r"[\u4e00-\u9fff]", plain))
        n_word = len(re.findall(r"[A-Za-z0-9]+", plain))
        words = n_cjk + n_word

        cover = folder / "cover.png"
        posts.append({
            "slug": folder.name,
            "dir": folder,
            "date": datetime.strptime(m.group(1), "%Y-%m-%d"),
            "title": title,
            "digest": digest,
            "words": words,
            "cover": "cover.png" if cover.exists() else "",
            "html": md_to_html(text),
        })
    posts.sort(key=lambda p: (p["date"], p["slug"]), reverse=True)
    return posts


# ---------- 样式 / 模板 ----------

CSS = r"""
:root{
  --accent:#3b5bfd;--accent-dark:#2f4be0;--violet:#7a3bfd;
  --ink:#171a21;--body:#3f3f46;--muted:#8a8f99;
  --bg:#f4f5f9;--card:#ffffff;--line:#e6e8ef;
  --hero1:#0c1130;--hero2:#1c2757;--radius:14px;
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%;scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--body);
  font-family:-apple-system,BlinkMacSystemFont,'Helvetica Neue','PingFang SC','Hiragino Sans GB','Microsoft YaHei',sans-serif;
  font-size:16px;line-height:1.75;letter-spacing:.3px}
a{color:var(--accent);text-decoration:none;transition:color .15s}
a:hover{color:var(--accent-dark)}
img{max-width:100%}
.container{max-width:1080px;margin:0 auto;padding:0 20px}

/* ---- 顶栏 ---- */
.site-header{position:sticky;top:0;z-index:50;background:rgba(255,255,255,.9);
  backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);border-bottom:1px solid var(--line)}
.header-inner{display:flex;align-items:center;justify-content:space-between;height:60px}
.brand{display:flex;align-items:center;gap:10px;color:var(--ink);font-weight:700;font-size:17px}
.brand:hover{color:var(--ink)}
.brand .dot{width:27px;height:27px;border-radius:8px;color:#fff;font-size:11.5px;font-weight:800;
  background:linear-gradient(135deg,var(--accent),var(--violet));display:flex;align-items:center;justify-content:center}
.btn{display:inline-flex;align-items:center;gap:6px;padding:8px 18px;border-radius:999px;
  background:var(--accent);color:#fff;font-size:14px;font-weight:600;cursor:pointer;
  transition:background .2s,transform .2s,box-shadow .2s}
.btn:hover{background:var(--accent-dark);color:#fff;transform:translateY(-1px);
  box-shadow:0 6px 16px rgba(59,91,253,.35)}

/* ---- 首页 hero ---- */
.hero{position:relative;overflow:hidden;color:#fff;
  background:radial-gradient(1100px 480px at 85% -10%,rgba(99,131,255,.38),transparent 60%),
             radial-gradient(700px 380px at -10% 110%,rgba(122,59,253,.25),transparent 55%),
             linear-gradient(135deg,var(--hero1),var(--hero2))}
.hero-inner{display:flex;align-items:center;justify-content:space-between;gap:40px;padding:66px 0 70px}
.hero h1{margin:0 0 10px;font-size:34px;line-height:1.3;font-weight:800;letter-spacing:1px}
.hero .slogan{margin:0 0 14px;font-size:16.5px;color:#aab6e8}
.hero .intro{margin:0 0 26px;font-size:14.5px;color:#8d9ac9;max-width:560px}
.hero .stats{display:flex;gap:26px;margin-top:30px;flex-wrap:wrap}
.hero .stat b{display:block;font-size:20px;color:#fff}
.hero .stat span{font-size:12.5px;color:#8d9ac9}
.hero .btn{padding:11px 28px;font-size:15px}
.qr-box{flex:0 0 auto;text-align:center}
.qr-box img,.qr-box .qr-placeholder{width:132px;height:132px;border-radius:12px;background:#fff;display:block}
.qr-box .qr-placeholder{border:2px dashed rgba(255,255,255,.45);background:rgba(255,255,255,.08);
  color:#aab6e8;font-size:12px;display:flex;align-items:center;justify-content:center;padding:10px}
.qr-box p{margin:10px 0 0;font-size:12.5px;color:#8d9ac9}
@media (max-width:760px){.hero-inner{flex-direction:column-reverse;text-align:center;padding:48px 0 54px}
  .hero h1{font-size:26px}.hero .intro{margin-inline:auto}.hero .stats{justify-content:center}}

/* ---- 文章列表 ---- */
.toolbar{display:flex;align-items:center;justify-content:space-between;gap:16px;
  margin:38px 0 22px;flex-wrap:wrap}
.toolbar h2{margin:0;font-size:21px;color:var(--ink);font-weight:700}
.toolbar .count{font-size:13px;color:var(--muted)}
.search{position:relative;flex:0 1 300px}
.search input{width:100%;padding:10px 16px 10px 38px;border:1px solid var(--line);border-radius:999px;
  background:var(--card);font-size:14px;color:var(--ink);outline:none;transition:border .2s,box-shadow .2s}
.search input:focus{border-color:var(--accent);box-shadow:0 0 0 3px rgba(59,91,253,.12)}
.search svg{position:absolute;left:13px;top:50%;transform:translateY(-50%);width:16px;height:16px;stroke:var(--muted)}
.card-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(298px,1fr));gap:24px;padding-bottom:64px}
.card{display:flex;flex-direction:column;background:var(--card);border:1px solid var(--line);
  border-radius:var(--radius);overflow:hidden;color:var(--body);transition:transform .22s,box-shadow .22s}
.card:hover{transform:translateY(-4px);box-shadow:0 16px 34px rgba(23,26,33,.10);color:var(--body)}
.card .cover-wrap{position:relative;aspect-ratio:2.35/1;background:linear-gradient(135deg,#1a2350,#0c1130);overflow:hidden}
.card .cover-wrap img{width:100%;height:100%;object-fit:cover;display:block}
.card .cover-wrap .latest{position:absolute;top:10px;left:10px;padding:3px 10px;border-radius:999px;
  background:rgba(59,91,253,.92);color:#fff;font-size:11.5px;font-weight:600;letter-spacing:1px}
.card .card-body{padding:18px 20px 20px;display:flex;flex-direction:column;flex:1}
.card .date{font-size:12.5px;color:var(--muted);margin-bottom:8px}
.card h3{margin:0 0 10px;font-size:17.5px;line-height:1.5;color:var(--ink);font-weight:700;
  display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.card .digest{margin:0;font-size:13.5px;line-height:1.8;color:var(--muted);
  display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
.card .more{margin-top:auto;padding-top:14px;font-size:13px;font-weight:600;color:var(--accent)}
.empty-tip{grid-column:1/-1;text-align:center;color:var(--muted);padding:48px 0;font-size:14px}

/* ---- 页脚 ---- */
.site-footer{border-top:1px solid var(--line);background:var(--card);padding:30px 0 36px;
  text-align:center;font-size:13px;color:var(--muted)}
.site-footer .fname{color:var(--ink);font-weight:700;margin-bottom:6px}
.site-footer p{margin:4px 0}

/* ---- 文章页 ---- */
.post-header{max-width:760px;margin:0 auto;padding:44px 22px 0}
.back{display:inline-flex;align-items:center;gap:6px;font-size:13.5px;color:var(--muted);margin-bottom:26px}
.back:hover{color:var(--accent)}
.post-header h1{margin:0 0 14px;font-size:25px;line-height:1.5;color:var(--ink);font-weight:800}
.post-meta{font-size:13.5px;color:var(--muted)}
.post-meta b{color:var(--accent);font-weight:600}
.post-banner{max-width:760px;margin:22px auto 0;padding:0 22px}
.post-banner img{width:100%;border-radius:12px;display:block}
.post-body{max-width:760px;margin:0 auto;padding:30px 22px 10px}
.post-body p{margin:17px 0;font-size:16px;line-height:1.95;letter-spacing:.4px;text-align:justify}
.post-body h2{margin:34px 0 14px;padding-left:12px;border-left:4px solid var(--accent);
  font-size:19px;font-weight:700;color:var(--ink);line-height:1.5}
.post-body h3{margin:24px 0 10px;font-size:16.5px;font-weight:700;color:var(--ink)}
.post-body strong{color:var(--ink);font-weight:700}
.post-body a{border-bottom:1px solid rgba(59,91,253,.35)}
.post-body code{margin:0 2px;padding:2px 6px;border-radius:4px;background:#f0f2f8;
  font-family:Consolas,'Courier New',monospace;font-size:13.5px;color:#c7254e}
.post-body ul,.post-body ol{margin:14px 0;padding-left:6px;list-style:none}
.post-body ul li,.post-body ol li{position:relative;padding:5px 0 5px 24px;margin:0;font-size:15.5px;line-height:1.9}
.post-body ul li::before{content:"";position:absolute;left:6px;top:16px;width:7px;height:7px;
  border-radius:2px;background:linear-gradient(135deg,var(--accent),var(--violet))}
.post-body ol{counter-reset:li}
.post-body ol li{counter-increment:li}
.post-body ol li::before{content:counter(li);position:absolute;left:0;top:5px;width:19px;height:19px;
  border-radius:6px;background:#eef1ff;color:var(--accent);font-size:12px;font-weight:700;
  display:flex;align-items:center;justify-content:center}
.post-body blockquote{margin:20px 0;padding:14px 18px;background:#f2f4ff;
  border-left:3px solid var(--accent);border-radius:0 10px 10px 0}
.post-body blockquote p{margin:6px 0;font-size:15px;color:#55607a}
.post-body figure{margin:26px 0;text-align:center}
.post-body figure img{border-radius:10px}
.post-body figcaption,.post-body .cap{margin:10px 0 0;font-size:13px;color:var(--muted);
  letter-spacing:.5px;text-align:center}
.post-body .table-wrap{margin:20px 0;overflow-x:auto}
.post-body table{border-collapse:collapse;width:100%;font-size:14px;background:var(--card)}
.post-body th{background:#eef1ff;color:var(--ink);font-weight:700}
.post-body th,.post-body td{border:1px solid #e4e7ee;padding:8px 12px;text-align:center}
.post-body tr:nth-child(even) td{background:#fafbfc}
.post-body pre{margin:20px 0;padding:16px 18px;border-radius:10px;overflow-x:auto;background:#282c34}
.post-body pre code{margin:0;padding:0;background:none;color:#abb2bf;font-size:13px;line-height:1.7;
  white-space:pre-wrap;font-family:Consolas,'Courier New',monospace}
.post-body hr.sep{margin:30px 0;border:none;border-top:1px dashed #d5d9e0}
.end-mark{max-width:760px;margin:26px auto 0;text-align:center;color:var(--muted);
  font-size:13px;letter-spacing:6px}
@media (max-width:640px){.post-body p{text-align:left}.post-header h1{font-size:21px}}

/* ---- 关注卡片 / 上下篇 ---- */
.follow-card{max-width:760px;margin:8px auto 0;display:flex;align-items:center;gap:22px;
  padding:26px 28px;border-radius:16px;color:#fff;overflow:hidden;position:relative;
  background:radial-gradient(600px 260px at 90% -20%,rgba(99,131,255,.4),transparent 60%),
             linear-gradient(135deg,var(--hero1),var(--hero2))}
.follow-card .qr-box img,.follow-card .qr-box .qr-placeholder{width:108px;height:108px;border-radius:10px}
.follow-card .qr-box .qr-placeholder{border:2px dashed rgba(255,255,255,.45)}
.follow-card h3{margin:0 0 8px;font-size:18px;font-weight:700;color:#fff}
.follow-card p{margin:0;font-size:13.5px;color:#aab6e8;line-height:1.8}
.follow-card .wid{display:inline-block;margin-top:10px;padding:4px 12px;border-radius:999px;
  background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.22);font-size:12.5px;color:#dfe5ff}
@media (max-width:640px){.follow-card{flex-direction:column;text-align:center;gap:16px}}

.pager{max-width:760px;margin:26px auto 0;padding:0 22px 56px;display:grid;
  grid-template-columns:1fr 1fr;gap:16px}
.pager a{display:flex;flex-direction:column;gap:6px;padding:16px 18px;background:var(--card);
  border:1px solid var(--line);border-radius:12px;color:var(--body);transition:border .2s,box-shadow .2s}
.pager a:hover{border-color:var(--accent);box-shadow:0 8px 20px rgba(59,91,253,.10);color:var(--body)}
.pager .tag{font-size:12px;color:var(--muted);letter-spacing:1px}
.pager .pt{font-size:14.5px;line-height:1.6;color:var(--ink);font-weight:600;
  display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.pager a.next{text-align:right}
.pager .placeholder{visibility:hidden}
@media (max-width:640px){.pager{grid-template-columns:1fr}.pager a.next{text-align:left}}
"""

FAVICON = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
<stop offset="0" stop-color="#3b5bfd"/><stop offset="1" stop-color="#7a3bfd"/></linearGradient></defs>
<rect width="64" height="64" rx="14" fill="url(#g)"/>
<path d="M24 12 L42 12 L31 32 L46 32 L21 53 L28 36 L16 36 Z" fill="#fff"/></svg>"""


def layout(cfg: dict, title: str, desc: str, body: str, depth: int, og_image: str = "") -> str:
    p = "../" * depth
    og = f'<meta property="og:image" content="{esc(og_image, True)}"/>' if og_image else ""
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc, True)}"/>
<meta property="og:title" content="{esc(title, True)}"/>
<meta property="og:description" content="{esc(desc, True)}"/>
{og}
<link rel="icon" type="image/svg+xml" href="{p}assets/favicon.svg"/>
<link rel="stylesheet" href="{p}assets/site.css"/>
</head>
<body>
{body}
</body>
</html>"""


def header(cfg: dict, follow_href: str = "#follow") -> str:
    return f"""<header class="site-header">
  <div class="container header-inner">
    <a class="brand" href="index.html"><span class="dot">AI</span>{esc(cfg['name'])}</a>
    <a class="btn" href="{follow_href}">+ 关注公众号</a>
  </div>
</header>"""


def footer(cfg: dict) -> str:
    note = f"<p>{esc(cfg['footer_note'])}</p>" if cfg.get("footer_note") else ""
    year = datetime.now().year
    return f"""<footer class="site-footer">
  <div class="container">
    <p class="fname">{esc(cfg['name'])} · {esc(cfg['slogan'])}</p>
    {note}
    <p>© {year} {esc(cfg['name'])} · 本站由 AI 内容流水线驱动生成</p>
  </div>
</footer>"""


def qr_block(cfg: dict, qr_src: str) -> str:
    if qr_src:
        img = f'<img src="{esc(qr_src, True)}" alt="{esc(cfg["name"], True)} 公众号二维码"/>'
    else:
        img = '<div class="qr-placeholder">二维码待配置<br/>（site.json）</div>'
    wid = f'<span class="wid">微信号：{esc(cfg["wechat_id"])}</span>' if cfg.get("wechat_id") else ""
    return img, wid


# ---------- 页面生成 ----------

def build_index(cfg: dict, posts: list[dict], qr_src: str) -> str:
    cards = []
    for idx, a in enumerate(posts):
        latest = '<span class="latest">最新</span>' if idx == 0 else ""
        if a["cover"]:
            cover = f'<img src="posts/{esc(a["slug"], True)}/cover.png" alt="{esc(a["title"], True)}" loading="lazy"/>'
        else:
            cover = ""
        cards.append(f"""<a class="card" href="posts/{esc(a['slug'], True)}/index.html"
  data-key="{esc((a['title'] + ' ' + a['digest']).lower(), True)}">
  <div class="cover-wrap">{cover}{latest}</div>
  <div class="card-body">
    <div class="date">{a['date'].strftime('%Y-%m-%d')}</div>
    <h3>{esc(a['title'])}</h3>
    <p class="digest">{esc(a['digest'])}</p>
    <span class="more">阅读全文 →</span>
  </div>
</a>""")

    qr_img, wid = qr_block(cfg, qr_src)
    latest_date = posts[0]["date"] if posts else None
    stats = f"""<div class="stats">
  <div class="stat"><b>{len(posts)}</b><span>篇文章</span></div>
  <div class="stat"><b>AI×人工</b><span>内容流水线</span></div>
  <div class="stat"><b>{latest_date.strftime('%m/%d') if latest_date else '--'}</b><span>最近更新</span></div>
</div>""" if posts else ""

    body = f"""{header(cfg, "#follow")}
<section class="hero">
  <div class="container hero-inner">
    <div class="hero-text">
      <h1>{esc(cfg['name'])}</h1>
      <p class="slogan">{esc(cfg['slogan'])}</p>
      <p class="intro">{esc(cfg['intro'])}</p>
      <a class="btn" href="#follow">+ 微信扫码关注</a>
      {stats}
    </div>
    <div class="qr-box">{qr_img}<p>微信扫码 · 关注公众号</p></div>
  </div>
</section>
<main class="container" id="list">
  <div class="toolbar">
    <div><h2>全部文章</h2><span class="count" id="count"></span></div>
    <div class="search">
      <svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round">
        <circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/></svg>
      <input id="search" type="search" placeholder="搜索文章标题 / 关键词" autocomplete="off"/>
    </div>
  </div>
  <div class="card-grid" id="grid">{''.join(cards) or '<div class="empty-tip">articles/ 下还没有文章</div>'}</div>
</main>
<div id="follow"></div>
<section class="hero" style="margin-top:-1px">
  <div class="container hero-inner" style="padding:44px 0 48px">
    <div class="hero-text">
      <h1 style="font-size:26px">关注「{esc(cfg['name'])}」</h1>
      <p class="slogan">{esc(cfg['slogan'])}</p>
      <p class="intro">网站更新可能滞后，最新内容第一时间发在公众号。{wid}</p>
    </div>
    <div class="qr-box">{qr_img}<p>长按识别 · 一起看 AI</p></div>
  </div>
</section>
{footer(cfg)}
<script>
(function(){{
  var grid=document.getElementById('grid'),count=document.getElementById('count'),
      cards=[].slice.call(grid.querySelectorAll('.card'));
  function fmt(n){{return n+' 篇文章';}}
  count.textContent=fmt(cards.length);
  document.getElementById('search').addEventListener('input',function(e){{
    var k=e.target.value.trim().toLowerCase(),n=0;
    cards.forEach(function(c){{
      var hit=!k||c.getAttribute('data-key').indexOf(k)>-1;
      c.style.display=hit?'':'none';if(hit)n++;
    }});
    var tip=grid.querySelector('.empty-tip');
    if(n===0){{if(!tip){{tip=document.createElement('div');tip.className='empty-tip';
      tip.textContent='没有匹配的文章，换个关键词试试';grid.appendChild(tip);}}}}
    else if(tip){{tip.remove();}}
    count.textContent=fmt(n);
  }});
}})();
</script>"""
    return layout(cfg, f"{cfg['name']} · {cfg['slogan']}", cfg["intro"], body, 0)


def follow_card(cfg: dict, qr_src: str) -> str:
    qr_img, wid = qr_block(cfg, qr_src)
    return f"""<section class="follow-card container" id="follow" style="margin-top:34px">
  <div class="qr-box">{qr_img}</div>
  <div>
    <h3>关注「{esc(cfg['name'])}」不迷路</h3>
    <p>{esc(cfg['slogan'])}。网站更新可能滞后，最新内容第一时间发在公众号。</p>
    {wid}
  </div>
</section>"""


def build_post(cfg: dict, a: dict, newer, older, qr_src: str) -> str:
    meta = (f'{a["date"].strftime("%Y-%m-%d")}&ensp;·&ensp;约 {a["words"]} 字'
            f'&ensp;·&ensp;<b>{esc(cfg["name"])}</b>')
    banner = (f'<div class="post-banner"><img src="{a["cover"]}" alt="{esc(a["title"], True)}"/></div>'
              if a["cover"] else "")

    def pager_entry(post, tag, cls, arrow=""):
        if post is None:
            return f'<a class="placeholder {cls}"><span class="tag">{tag}</span><span class="pt">-</span></a>'
        return (f'<a class="{cls}" href="../{esc(post["slug"], True)}/index.html">'
                f'<span class="tag">{tag}{arrow}</span><span class="pt">{esc(post["title"])}</span></a>')

    body = f"""{header(cfg)}
<article>
  <div class="post-header">
    <a class="back" href="../index.html">← 返回首页</a>
    <h1>{esc(a['title'])}</h1>
    <div class="post-meta">{meta}</div>
  </div>
  {banner}
  <div class="post-body">{a['html']}</div>
</article>
<div class="end-mark container">— END —</div>
{follow_card(cfg, qr_src)}
<nav class="pager">
  {pager_entry(older, '上一篇', 'prev')}
  {pager_entry(newer, '下一篇', 'next')}
</nav>
{footer(cfg)}"""
    return layout(cfg, f"{a['title']} · {cfg['name']}", a["digest"], body, 2,
                  og_image=f"../{a['slug']}/cover.png" if a["cover"] else "")


def build_rss(cfg: dict, posts: list[dict]) -> str:
    from email.utils import formatdate
    base = cfg["base_url"].rstrip("/")
    items = []
    for a in posts:
        link = f"{base}/posts/{a['slug']}/"
        items.append(f"""    <item>
      <title>{esc(a['title'], True)}</title>
      <link>{esc(link, True)}</link>
      <guid isPermaLink="true">{esc(link, True)}</guid>
      <pubDate>{formatdate(datetime(a['date'].year, a['date'].month, a['date'].day, 9, 0, 0).timestamp(), usegmt=True)}</pubDate>
      <description>{esc(a['digest'], True)}</description>
    </item>""")
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>{esc(cfg['name'], True)}</title>
    <link>{esc(base, True)}</link>
    <description>{esc(cfg['slogan'], True)}</description>
    <language>zh-CN</language>
{''.join(items)}
  </channel>
</rss>
"""


# ---------- 主流程 ----------

def clean_out() -> None:
    """清空输出目录。Windows 下预览服务器若占用 site/ 根目录，降级为清空内容原地重建。"""
    if not OUT.exists():
        return
    try:
        shutil.rmtree(OUT)
    except PermissionError:
        for child in OUT.iterdir():
            if child.is_dir():
                shutil.rmtree(child, ignore_errors=True)
            else:
                child.unlink(missing_ok=True)
        print("  （site/ 根目录被占用（多半开着预览服务器），已清空内容并原地重建）")


def build() -> None:
    cfg = load_config()
    posts = collect_articles()

    clean_out()
    (OUT / "assets").mkdir(parents=True, exist_ok=True)
    (OUT / "posts").mkdir(exist_ok=True)

    (OUT / "assets" / "site.css").write_text(CSS, encoding="utf-8")
    (OUT / "assets" / "favicon.svg").write_text(FAVICON, encoding="utf-8")

    # 二维码复制到 assets；首页与文章页目录层级不同，相对地址分别传参
    qr_name = ""
    if cfg.get("qr_image"):
        qr_path = ROOT / cfg["qr_image"]
        if qr_path.exists():
            qr_name = qr_path.name
            shutil.copy2(qr_path, OUT / "assets" / qr_name)

    for idx, a in enumerate(posts):
        d = OUT / "posts" / a["slug"]
        d.mkdir(exist_ok=True)
        for f in a["dir"].iterdir():
            if f.suffix.lower() in IMG_EXTS:
                shutil.copy2(f, d / f.name)
        newer = posts[idx - 1] if idx > 0 else None
        older = posts[idx + 1] if idx + 1 < len(posts) else None
        post_qr = f"../../assets/{qr_name}" if qr_name else ""
        (d / "index.html").write_text(build_post(cfg, a, newer, older, post_qr), encoding="utf-8")

    (OUT / "index.html").write_text(
        build_index(cfg, posts, f"assets/{qr_name}" if qr_name else ""), encoding="utf-8")

    if cfg.get("base_url"):
        (OUT / "feed.xml").write_text(build_rss(cfg, posts), encoding="utf-8")

    print(f"[build_site] {len(posts)} 篇文章 -> {OUT}")
    for a in posts:
        print(f"  - {a['date'].date()}  {a['title']}")
    if not cfg.get("base_url"):
        print("  （site.json 未配置 base_url，未生成 RSS；配置后重新构建即可）")


def serve(port: int = 8740) -> None:
    import functools
    import http.server
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(OUT))
    print(f"预览地址: http://127.0.0.1:{port}/  （Ctrl+C 退出）")
    http.server.ThreadingHTTPServer(("127.0.0.1", port), handler).serve_forever()


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    args = sys.argv[1:]
    build()
    if "--serve" in args:
        i = args.index("--serve")
        port = int(args[i + 1]) if len(args) > i + 1 and args[i + 1].isdigit() else 8740
        serve(port)


if __name__ == "__main__":
    main()

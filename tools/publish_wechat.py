#!/usr/bin/env python3
"""把一篇文章目录推送成公众号草稿箱里的完整图文（人只负责最后点发布）。

用法:
  python tools/publish_wechat.py articles/2026-09-22-三巨头AI安全联盟

做四件事:
  1. 取 access_token（本地缓存 7000 秒，自动续期）
  2. 文内图片 fig*.png 逐张上传（uploadimg，拿微信托管的 URL 替换进正文）
  3. 封面 cover.png 上传为永久素材（拿 thumb_media_id）
  4. 标题/摘要/正文打包调草稿箱接口 draft/add

前置: wechat.json 配好 appid/appsecret；本机出口 IP 在白名单里
（换网络/开关 VPN 会变 IP，报 40164 就去开发者平台更新白名单）。
"""
from __future__ import annotations

import json
import mimetypes
import pathlib
import re
import sys
import time
import urllib.parse
import urllib.request
import uuid

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import md2wechat  # noqa: E402  复用现有排版器（内联样式版）

API = "https://api.weixin.qq.com"
TOKEN_CACHE = ROOT / ".wechat_token.json"

ERR_HINTS = {
    40001: "AppSecret 不正确，检查 wechat.json（或在开发者平台重置后更新）",
    40164: "本机出口 IP 不在白名单（VPN 开关/换网络都会变 IP），去开发者平台更新白名单",
    45009: "接口调用次数超限，稍后再试",
    48001: "该账号无此接口权限",
}


def load_cfg() -> dict:
    cfg = json.loads((ROOT / "wechat.json").read_text(encoding="utf-8"))
    if not cfg.get("appid") or not cfg.get("appsecret"):
        sys.exit("wechat.json 里 appid/appsecret 还没配置")
    return cfg


def http_json(url: str, data: bytes | None = None) -> dict:
    req = urllib.request.Request(url, data=data, method="POST" if data else "GET")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def check(resp: dict, step: str) -> dict:
    if resp.get("errcode"):
        code = resp["errcode"]
        hint = ERR_HINTS.get(code, "")
        sys.exit(f"[失败] {step}: errcode={code} {resp.get('errmsg','')}\n       {hint}")
    return resp


def get_token(cfg: dict) -> str:
    if TOKEN_CACHE.exists():
        try:
            c = json.loads(TOKEN_CACHE.read_text(encoding="utf-8"))
            if c.get("appid") == cfg["appid"] and time.time() < c.get("expires_at", 0) - 120:
                return c["token"]
        except Exception:
            pass
    q = urllib.parse.urlencode({"grant_type": "client_credential",
                                "appid": cfg["appid"], "secret": cfg["appsecret"]})
    resp = check(http_json(f"{API}/cgi-bin/token?{q}"), "获取 access_token")
    token = resp["access_token"]
    TOKEN_CACHE.write_text(json.dumps({
        "appid": cfg["appid"], "token": token,
        "expires_at": time.time() + resp.get("expires_in", 7200),
    }), encoding="utf-8")
    return token


def upload(token: str, endpoint: str, path: pathlib.Path) -> dict:
    """multipart/form-data 上传一个文件（stdlib 手拼）。"""
    boundary = uuid.uuid4().hex
    ct = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    fn = path.name.encode("ascii", "replace").decode()
    body = b"".join([
        f"--{boundary}\r\n".encode(),
        f'Content-Disposition: form-data; name="media"; filename="{fn}"\r\n'.encode(),
        f"Content-Type: {ct}\r\n\r\n".encode(),
        path.read_bytes(),
        f"\r\n--{boundary}--\r\n".encode(),
    ])
    req = urllib.request.Request(
        f"{API}{endpoint}?access_token={token}", data=body, method="POST")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def extract_meta(md_text: str) -> tuple[str, str]:
    title = ""
    digest = ""
    for ln in md_text.splitlines():
        s = ln.strip()
        if not title:
            m = re.match(r"^#\s+(.*)", s)
            if m:
                title = m.group(1).strip()
                continue
        if not digest and s and not re.match(r"^(#|```|\s*>|\s*[-*+]\s|\s*\d+[.、]\s|!\[|▲|\|)", s):
            digest = re.sub(r"\s+", " ", re.sub(r"(\*\*|\*|`)", "", s))
    return title[:64], (digest[:117] + "…") if len(digest) > 120 else digest


def render_body(md_text: str) -> str:
    """md2wechat 输出整页 HTML，这里取正文 section 的内层。"""
    page = md2wechat.convert(md_text)
    m = re.search(r'border-radius:12px;font-family:[^>]*">(.*)</section></body>', page, re.S)
    if not m:
        sys.exit("[失败] 排版结果解析异常（md2wechat 输出格式变了？）")
    return m.group(1)


def push(article_dir: pathlib.Path) -> dict:
    """推送一篇文章到公众号草稿箱。成功返回 {"title","digest","media_id","figs"}。"""
    md_file = article_dir / "article.md"
    if not md_file.exists():
        raise RuntimeError(f"找不到 {md_file}")

    cfg = load_cfg()
    token = get_token(cfg)

    md_text = md_file.read_text(encoding="utf-8")
    title, digest = extract_meta(md_text)
    body = render_body(md_text)

    figs = sorted(set(re.findall(r'src="([^"]+)"', body)))
    n_figs = 0
    for src in figs:
        if src.startswith(("http://", "https://")):
            continue
        f = article_dir / src
        if not f.exists():
            print(f"  [跳过] 正文引用的 {src} 不存在")
            continue
        resp = check(upload(token, "/cgi-bin/media/uploadimg", f), f"上传文内图 {src}")
        body = body.replace(src, resp["url"])
        n_figs += 1
        print(f"  [图] {src} -> 微信图床 OK")

    cover = article_dir / "cover.png"
    if not cover.exists():
        raise RuntimeError("缺 cover.png 封面")
    resp = check(upload(token, "/cgi-bin/material/add_material", cover), "上传封面")
    print("  [封面] thumb_media_id OK")

    payload = {"articles": [{
        "title": title,
        "author": cfg.get("author", ""),
        "digest": digest,
        "content": body,
        "content_source_url": cfg.get("source_url", ""),
        "thumb_media_id": resp["media_id"],
        "need_open_comment": 0,
        "only_fans_can_comment": 0,
    }]}
    resp = check(http_json(f"{API}/cgi-bin/draft/add?access_token={token}",
                           json.dumps(payload, ensure_ascii=False).encode("utf-8")), "创建草稿")
    return {"title": title, "digest": digest, "media_id": resp["media_id"], "figs": n_figs}


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    r = push(pathlib.Path(sys.argv[1]))
    print(f"\n[成功] 《{r['title']}》已进入公众号草稿箱（media_id={r['media_id']}）")
    print("手机「公众平台助手」小程序 或 mp.weixin.qq.com 后台 → 草稿箱：预览确认后点发布。")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""公众号发布中枢的 MCP Server（stdio 传输，纯标准库，零依赖）。

把局域网发布中枢的能力暴露成 MCP 工具，任何支持 MCP 的客户端
（ZCode / Claude Desktop / Cline 等）配置后即可原生调用。

配置（以 ZCode / Claude Desktop 为例，mcpServers 里加一项）:
  {
    "gongzhonghao": {
      "command": "python",
      "args": ["/path/to/gongzhonghao/tools/mcp_server.py"],
      "env": {
        "HUB_URL": "http://10.168.1.109:8741",
        "HUB_TOKEN": "<中枢token>"
      }
    }
  }

环境变量:
  HUB_URL   中枢地址，默认 http://10.168.1.109:8741
  HUB_TOKEN 中枢写接口 Token；不设则尝试读项目根 .dashboard_auth.json（仅中枢机本机有）

提供的工具:
  list_articles  已发文章列表（防选题撞车）
  read_backlog   选题池 topics/backlog.md
  add_topic      向选题池登记新选题（防多agent撞车）
  read_article   读某篇已有文章全文
  list_drafts    公众号草稿箱列表
  submit_article 提交新文章（markdown+配图base64），默认直接推送草稿箱
  push_article   重推 articles/ 下某个已有文章
  get_records    操作记录
  hub_status     中枢状态（出口IP/token/草稿箱数）
  build_site     重建发布网站
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
import urllib.error
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
HUB_URL = os.environ.get("HUB_URL", "http://10.168.1.109:8741").rstrip("/")


def _token() -> str:
    t = os.environ.get("HUB_TOKEN")
    if t:
        return t.strip()
    f = ROOT / ".dashboard_auth.json"
    if f.exists():
        try:
            return json.loads(f.read_text(encoding="utf-8"))["token"]
        except Exception:
            pass
    return ""


TOKEN = _token()


def api(path: str, payload: dict | None = None) -> dict:
    """GET（payload=None）/ 带认证 POST。submit 传图可能较大，超时给足。"""
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(HUB_URL + path, data=data,
                                 method="POST" if data is not None else "GET")
    if data is not None:
        req.add_header("Content-Type", "application/json")
        if TOKEN:
            req.add_header("X-Auth", TOKEN)
    timeout = 180 if path == "/api/submit" else 30
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode("utf-8")[:300]
        except Exception:
            detail = str(e)
        raise RuntimeError(f"HTTP {e.code}: {detail}")
    except Exception as e:
        raise RuntimeError(f"请求中枢失败（{HUB_URL}{path}）: {e}")


# ---------- 工具实现 ----------

def t_list_articles(a: dict) -> str:
    arts = api("/api/articles")
    if not arts:
        return "还没有文章"
    lines = [f'{x["date"]}  {x["title"]}  （{x["figs"]}图{"，已推送" if x["pushed"] else "，未推送"}）'
             for x in arts]
    return f"共 {len(arts)} 篇：\n" + "\n".join(lines)


def t_read_backlog(a: dict) -> str:
    return api("/api/backlog").get("content", "") or "（选题池为空）"


def t_add_topic(a: dict) -> str:
    if not TOKEN:
        raise RuntimeError("未配置 HUB_TOKEN")
    r = api("/api/backlog", {"topic": a["topic"], "note": a.get("note", ""),
                             "agent": a.get("agent", "mcp")})
    return f"选题已登记进选题池（状态 ✍️）：{r['topic']}\n写完后提交文章；选题池是防撞车的唯一依据"


def t_read_article(a: dict) -> str:
    r = api("/api/article?dir=" + urllib.parse.quote(a["dir"]))
    md = r.get("markdown", "")
    return md if md else "（文章为空）"


def t_list_drafts(a: dict) -> str:
    r = api("/api/drafts")
    if "error" in r:
        raise RuntimeError("草稿箱读取失败: " + r["error"])
    items = r.get("items", [])
    if not items:
        return "草稿箱为空"
    lines = [f'{x["update"]}  {x["title"]}' for x in items]
    return f"草稿箱共 {r.get('total')} 篇（最新 {len(items)} 篇）：\n" + "\n".join(lines)


def t_submit_article(a: dict) -> str:
    if not TOKEN:
        raise RuntimeError("未配置 HUB_TOKEN（向管理员索取，配到环境变量或本机 .dashboard_auth.json）")
    payload = dict(a)
    payload.setdefault("push", True)
    payload.setdefault("agent", "mcp")
    r = api("/api/submit", payload)
    if r.get("pushed"):
        return (f"已提交并推送草稿箱：\n目录 {r['dir']}\nmedia_id {r['media_id']}\n"
                f"提醒：草稿→正式群发需公众号管理员在手机「公众平台助手」确认（微信对个人号不放开API发布）")
    return f"已提交（未推送）：目录 {r['dir']}，到中枢网页上点「推送草稿」"


def t_push_article(a: dict) -> str:
    if not TOKEN:
        raise RuntimeError("未配置 HUB_TOKEN")
    r = api("/api/push", {"dir": a["dir"]})
    return f"已推送草稿箱：{r.get('title','')} media_id={r.get('media_id','')}"


def t_get_records(a: dict) -> str:
    recs = api("/api/records")[: int(a.get("limit", 15))]
    if not recs:
        return "暂无记录"
    return "\n".join(f'{r["at"]} [{r["action"]}{"✓" if r.get("ok") else "✗"}] '
                     f'{r.get("title") or r.get("dir") or ""} {r.get("agent") or ""}'
                     f'{"" if r.get("ok") else " 错误:" + str(r.get("error", ""))[:80]}'
                     for r in recs)


def t_hub_status(a: dict) -> str:
    s = api("/api/status")
    return (f"出口IP: {s.get('ip')} {s.get('ip_loc','')}\n"
            f"token: {s.get('token')}\n草稿箱: {s.get('drafts')}\n"
            f"（出口IP需在微信白名单内，否则推送报40164）")


def t_build_site(a: dict) -> str:
    if not TOKEN:
        raise RuntimeError("未配置 HUB_TOKEN")
    r = api("/api/build", {})
    return f"网站已重建，共 {r.get('articles')} 篇"


TOOLS = [
    {
        "name": "list_articles",
        "description": "列出公众号已有文章（日期/标题/配图数/是否已推送）。写稿前先查，避免选题撞车。",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": t_list_articles,
    },
    {
        "name": "read_backlog",
        "description": "读取选题池（topics/backlog.md，含状态：💡待写/✍️写作中/✅已发/❌放弃）和账号方向说明。",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": t_read_backlog,
    },
    {
        "name": "add_topic",
        "description": "向选题池登记一个新选题（状态 ✍️）。选题与池中已有内容相似会被拒绝（防多agent撞车）。"
                      "开工写某选题前先登记，写完用 submit_article 提交。",
        "inputSchema": {"type": "object", "required": ["topic"],
                        "properties": {"topic": {"type": "string", "description": "选题，一句话"},
                                       "note": {"type": "string", "description": "备注（角度/来源）"},
                                       "agent": {"type": "string", "description": "你的agent名字"}}},
        "handler": t_add_topic,
    },
    {
        "name": "read_article",
        "description": "读取某篇已有文章的完整 markdown（参考风格、做互链、检查一致性时用）。dir 从 list_articles 获取。",
        "inputSchema": {"type": "object", "required": ["dir"],
                        "properties": {"dir": {"type": "string", "description": "文章目录名，如 2026-09-22-三巨头AI安全联盟"}}},
        "handler": t_read_article,
    },
    {
        "name": "list_drafts",
        "description": "查看公众号草稿箱里的草稿（标题+更新时间），核实提交结果。",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": t_list_drafts,
    },
    {
        "name": "submit_article",
        "description": "提交一篇新文章到发布中枢。默认 push=true 直接进公众号草稿箱（无需人工确认）。"
                      "规范：标题≤30字；正文1300~2000字、段落短；配图 fig*.png 与 markdown 引用名一致；"
                      "正文不放外链；文末加参考资料和引导关注段。",
        "inputSchema": {
            "type": "object",
            "required": ["title", "markdown", "cover_b64"],
            "properties": {
                "title": {"type": "string", "description": "文章标题，≤30字"},
                "markdown": {"type": "string",
                             "description": "正文markdown。配图 ![说明](fig1-xxx.png)；图注行以▲开头；小节##；重点**加粗**；引用>；列表-"},
                "cover_b64": {"type": "string", "description": "封面PNG(900×383)的base64"},
                "figs": {"type": "array",
                         "description": "文内配图列表",
                         "items": {"type": "object",
                                   "required": ["name", "b64"],
                                   "properties": {"name": {"type": "string", "description": "如 fig1-xxx.png"},
                                                  "b64": {"type": "string", "description": "图片base64"}}}},
                "digest": {"type": "string", "description": "摘要，默认取首段"},
                "push": {"type": "boolean", "default": True,
                         "description": "true=直接推送公众号草稿箱；false=只落盘等人工网页推送"},
                "agent": {"type": "string", "description": "你的agent名字，用于操作记录"},
                "date": {"type": "string", "description": "YYYY-MM-DD，默认今天"},
            },
        },
        "handler": t_submit_article,
    },
    {
        "name": "push_article",
        "description": "把 articles/ 下已有文章重新推送到公众号草稿箱（会生成新草稿）。",
        "inputSchema": {"type": "object", "required": ["dir"],
                        "properties": {"dir": {"type": "string", "description": "文章目录名，如 2026-09-22-三巨头AI安全联盟"}}},
        "handler": t_push_article,
    },
    {
        "name": "get_records",
        "description": "查看中枢操作记录（提交/推送/构建，谁做的、成功与否）。",
        "inputSchema": {"type": "object", "properties": {"limit": {"type": "number", "default": 15}}},
        "handler": t_get_records,
    },
    {
        "name": "hub_status",
        "description": "中枢状态：出口IP（需在微信白名单）、token 状态、草稿箱数量。",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": t_hub_status,
    },
    {
        "name": "build_site",
        "description": "重建发布网站（聚合 articles/ 全部文章）。",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": t_build_site,
    },
]
TOOLS_BY_NAME = {t["name"]: t for t in TOOLS}


# ---------- MCP stdio 协议（JSON-RPC 2.0，按行分隔） ----------

def handle(msg: dict) -> dict | None:
    method = msg.get("method", "")
    mid = msg.get("id")
    if method in ("notifications/initialized", "notifications/cancelled"):
        return None
    if method == "initialize":
        return {"jsonrpc": "2.0", "id": mid, "result": {
            "protocolVersion": msg.get("params", {}).get("protocolVersion", "2024-11-05"),
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "gongzhonghao-hub", "version": "1.0.0"},
        }}
    if method == "ping":
        return {"jsonrpc": "2.0", "id": mid, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": mid, "result": {
            "tools": [{"name": t["name"], "description": t["description"],
                       "inputSchema": t["inputSchema"]} for t in TOOLS]}}
    if method == "tools/call":
        params = msg.get("params", {})
        tool = TOOLS_BY_NAME.get(params.get("name", ""))
        if not tool:
            return {"jsonrpc": "2.0", "id": mid, "result": {
                "content": [{"type": "text", "text": f"未知工具: {params.get('name')}"}],
                "isError": True}}
        try:
            text = tool["handler"](params.get("arguments") or {})
            return {"jsonrpc": "2.0", "id": mid, "result": {
                "content": [{"type": "text", "text": text}], "isError": False}}
        except Exception as e:
            return {"jsonrpc": "2.0", "id": mid, "result": {
                "content": [{"type": "text", "text": f"{type(e).__name__}: {e}"}],
                "isError": True}}
    if mid is not None:  # 未知请求
        return {"jsonrpc": "2.0", "id": mid,
                "error": {"code": -32601, "message": f"method not found: {method}"}}
    return None


def main() -> None:
    try:
        sys.stdin.reconfigure(encoding="utf-8", errors="replace")
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            resp = handle(json.loads(line))
        except Exception as e:
            resp = {"jsonrpc": "2.0", "id": None,
                    "error": {"code": -32700, "message": f"parse error: {e}"}}
        if resp is not None:
            sys.stdout.write(json.dumps(resp, ensure_ascii=True) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""以标准 MCP 客户端身份完整自检 tools/mcp_server.py（纯协议层测试，不碰内部实现）。

用法:
  python tools/mcp_client_test.py                          # stdio 全量测试（本机中枢 127.0.0.1:8741）
  HUB_URL=http://10.168.1.109:8741 python tools/mcp_client_test.py   # 指定中枢
  SKIP_SUBMIT=1 python tools/mcp_client_test.py            # 跳过写测试（只读自检，不留文件）
  MCP_TRANSPORT=http python tools/mcp_client_test.py       # 测 HTTP MCP 端点（POST /mcp）
"""
from __future__ import annotations

import base64
import json
import os
import pathlib
import queue
import subprocess
import sys
import threading
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent


class McpClient:
    """最小标准 MCP stdio 客户端：spawn 子进程 + 行分隔 JSON-RPC。"""

    def __init__(self, hub_url: str):
        env = {**os.environ, "HUB_URL": hub_url}
        self.proc = subprocess.Popen(
            [sys.executable, str(ROOT / "tools" / "mcp_server.py")],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, encoding="utf-8", env=env)
        self.q: "queue.Queue[str]" = queue.Queue()
        threading.Thread(target=self._reader, daemon=True).start()
        self._id = 0

    def _reader(self) -> None:
        for line in self.proc.stdout:
            self.q.put(line.strip())

    def request(self, method: str, params: dict | None = None, timeout: float = 60) -> dict:
        self._id += 1
        mid = self._id
        msg: dict = {"jsonrpc": "2.0", "id": mid, "method": method}
        if params is not None:
            msg["params"] = params
        self.proc.stdin.write(json.dumps(msg) + "\n")
        self.proc.stdin.flush()
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                line = self.q.get(timeout=max(0.2, deadline - time.time()))
            except queue.Empty:
                break
            d = json.loads(line)
            if d.get("id") == mid:
                return d
        raise TimeoutError(f"{method} 响应超时（{timeout}s）")

    def notify(self, method: str) -> None:
        self.proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": method}) + "\n")
        self.proc.stdin.flush()

    def call(self, name: str, args: dict | None = None, timeout: float = 60) -> dict:
        return self.request("tools/call", {"name": name, "arguments": args or {}}, timeout)

    def close(self) -> None:
        try:
            self.proc.stdin.close()
        except Exception:
            pass
        self.proc.terminate()


def http_test() -> int:
    """MCP_TRANSPORT=http：以标准 Streamable HTTP 客户端身份测 POST /mcp 端点。"""
    import urllib.request
    import urllib.error
    hub = os.environ.get("HUB_URL", "http://127.0.0.1:8741")
    url = hub.rstrip("/") + "/mcp"
    token = os.environ.get("HUB_TOKEN") or _local_token()
    print(f"MCP HTTP 端点自检  (url={url})")
    ok = fail = 0

    def check(name, cond, detail=""):
        nonlocal ok, fail
        print(f"  [{'✓' if cond else '✗'}] {name}" + (f"   {detail}" if detail else ""))
        ok, fail = ok + bool(cond), fail + (not cond)

    def post(msg, headers=None, timeout=60):
        req = urllib.request.Request(
            url, data=json.dumps(msg).encode("utf-8"), method="POST",
            headers={"Content-Type": "application/json",
                     "Accept": "application/json, text/event-stream", **(headers or {})})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8"))

    _id = 0

    def req(method, params=None):
        nonlocal _id
        _id += 1
        st, d = post({"jsonrpc": "2.0", "id": _id, "method": method, **({"params": params} if params else {})},
                     headers={"Authorization": f"Bearer {token}"} if token else {})
        return d

    # 1) 无 Token → 401
    try:
        post({"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {}})
        check("无Token被拒绝", False, "竟然放行了")
    except urllib.error.HTTPError as e:
        check("无Token被拒绝(401)", e.code == 401)

    # 2) 标准握手
    r = req("initialize", {"protocolVersion": "2025-03-26", "capabilities": {},
                           "clientInfo": {"name": "http-test", "version": "1.0"}})
    si = r.get("result", {}).get("serverInfo", {})
    check("initialize 握手(HTTP)", si.get("name") == "gongzhonghao-hub",
          f"server={si.get('name')}, 协议={r['result'].get('protocolVersion')}")

    # 3) 工具发现 + 调用
    tools = req("tools/list").get("result", {}).get("tools", [])
    check("tools/list = 10 个工具(HTTP)", len(tools) == 10)
    r = req("tools/call", {"name": "hub_status", "arguments": {}})
    check("tools/call hub_status(HTTP)", not r["result"]["isError"],
          r["result"]["content"][0]["text"].splitlines()[0])

    # 4) GET /mcp → 405（规范行为）
    try:
        urllib.request.urlopen(url, timeout=15)
        check("GET /mcp 返回 405", False, "竟然200了")
    except urllib.error.HTTPError as e:
        check("GET /mcp 返回 405", e.code == 405)

    print(f"\n结果: {ok} 通过, {fail} 失败")
    return 1 if fail else 0


def _local_token() -> str:
    f = ROOT / ".dashboard_auth.json"
    if f.exists():
        try:
            return json.loads(f.read_text(encoding="utf-8"))["token"]
        except Exception:
            pass
    return ""


def main() -> None:
    if os.environ.get("MCP_TRANSPORT") == "http":
        sys.exit(http_test())
    hub = os.environ.get("HUB_URL", "http://127.0.0.1:8741")
    skip_submit = os.environ.get("SKIP_SUBMIT") == "1"
    print(f"MCP 标准客户端自检  (hub={hub}{', 跳过写测试' if skip_submit else ''})")
    c = McpClient(hub)
    ok = fail = 0

    def check(name: str, cond: bool, detail: str = "") -> None:
        nonlocal ok, fail
        print(f"  [{'✓' if cond else '✗'}] {name}" + (f"   {detail}" if detail else ""))
        ok, fail = ok + bool(cond), fail + (not cond)

    def text(r: dict) -> str:
        return r["result"]["content"][0]["text"]

    # 1. 标准握手
    r = c.request("initialize", {"protocolVersion": "2024-11-05", "capabilities": {},
                                 "clientInfo": {"name": "mcp-client-test", "version": "1.0"}})
    si = r.get("result", {}).get("serverInfo", {})
    check("initialize 握手", si.get("name") == "gongzhonghao-hub",
          f"server={si.get('name')} v{si.get('version')}, 协议={r['result'].get('protocolVersion')}")
    c.notify("notifications/initialized")
    check("notifications/initialized（无需响应）", True)

    # 2. ping
    check("ping", "result" in c.request("ping"))

    # 3. 工具发现
    tools = c.request("tools/list").get("result", {}).get("tools", [])
    names = [t["name"] for t in tools]
    check("tools/list 返回 10 个工具", len(tools) == 10, "、".join(names))
    sub = next((t for t in tools if t["name"] == "submit_article"), None)
    check("submit_article 含 inputSchema",
          bool(sub and sub.get("inputSchema", {}).get("properties")))

    # 4. 只读工具
    r = c.call("hub_status")
    check("hub_status", not r["result"]["isError"], text(r).splitlines()[0])
    r = c.call("list_articles")
    check("list_articles", text(r).startswith("共 "), text(r).splitlines()[0])
    r = c.call("read_backlog")
    check("read_backlog", "选题池" in text(r), f"{len(text(r))} 字符")
    r = c.call("get_records", {"limit": 3})
    check("get_records", not r["result"]["isError"], text(r).splitlines()[0][:46])
    r = c.call("read_article", {"dir": "2026-09-22-三巨头AI安全联盟"})
    check("read_article", not r["result"]["isError"] and text(r).lstrip().startswith("#"),
          f"{len(text(r))} 字符")
    r = c.call("read_article", {"dir": "../wechat.json"})
    check("read_article 路径穿越被拦截", r["result"].get("isError") is True)
    r = c.call("list_drafts")
    check("list_drafts", not r["result"]["isError"], text(r).splitlines()[0][:46])

    # 5. 写工具：提交测试文章（push=false，不进草稿箱；SKIP_SUBMIT=1 跳过）
    if not skip_submit:
        art = ROOT / "articles" / "2026-09-21-GPT6-Astra发布"
        r = c.call("submit_article", {
            "title": "【MCP自检】标准客户端链路测试",
            "markdown": "MCP 标准客户端自检创建的临时文章，测完即删。\n\n![测试图](fig1-stats.png)\n\n▲ 图1 · 测试配图",
            "cover_b64": base64.b64encode((art / "cover.png").read_bytes()).decode(),
            "figs": [{"name": "fig1-stats.png",
                      "b64": base64.b64encode((art / "fig1-stats.png").read_bytes()).decode()}],
            "push": False, "agent": "mcp-client-test"}, timeout=120)
        check("submit_article (push=false)", not r["result"]["isError"] and "已提交" in text(r),
              text(r).splitlines()[0])
        r = c.call("add_topic", {"topic": "【MCP自检】临时选题登记测试", "agent": "mcp-client-test"})
        check("add_topic", not r["result"]["isError"] and "已登记" in text(r), text(r).splitlines()[0])
        r = c.call("add_topic", {"topic": "GPT-6 Astra 发布", "agent": "mcp-client-test"})
        check("add_topic 撞车被拒绝", r["result"].get("isError") is True,
              text(r).splitlines()[0][:52])

    # 6. 协议错误路径
    r = c.call("no_such_tool")
    check("未知工具 → isError=true", r["result"].get("isError") is True)
    r = c.request("madeup/method")
    check("未知方法 → JSON-RPC -32601", r.get("error", {}).get("code") == -32601)

    c.close()
    print(f"\n结果: {ok} 通过, {fail} 失败")
    sys.exit(1 if fail else 0)


if __name__ == "__main__":
    main()

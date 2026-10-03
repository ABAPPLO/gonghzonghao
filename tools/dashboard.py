#!/usr/bin/env python3
"""公众号发布中枢（局域网）：本机持有凭据，其他 agent / 浏览器都能发布。

用法:
  python tools/dashboard.py            # http://<本机局域网IP>:8741
  python tools/dashboard.py 9000       # 指定端口

三种使用方式:
  1. 网页:  打开地址即发布台（预览/推送/重建网站/操作记录）
  2. 命令行同机: python tools/publish_wechat.py articles/xxx
  3. 局域网 agent: POST /api/submit 提交整篇文章（Markdown+配图base64），push=true 直接进草稿箱

接口（写操作需请求头 X-Auth: <token>，token 首次启动自动生成并打印，存在 .dashboard_auth.json）:
  GET  /api/articles          文章列表
  GET  /api/status            出口IP/token状态/草稿箱数
  GET  /api/records           操作记录（最近100条）
  GET  /api/backlog           选题池 topics/backlog.md 内容
  POST /api/push     {dir}                                            推送已有文章到草稿箱
  POST /api/submit   {title,markdown,digest?,cover_b64,figs:[{name,b64}],push?,agent?,date?}
                                                                    接收新文章并可选直接推送
  POST /api/build    {}                                              重建网站
  GET  /preview/<dir>/<file>                                          预览文章目录文件

安全: 只监听局域网场景；写操作必须带 Token；wechat.json 凭据永远不出本机。
"""
from __future__ import annotations

import base64
import html
import http.server
import json
import mimetypes
import os
import pathlib
import re
import socket
import sys
import threading
import time
import urllib.parse
import urllib.request
import uuid
from datetime import datetime

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import publish_wechat  # noqa: E402

ARTICLES = ROOT / "articles"
PUSH_LOG = ROOT / ".push_log.json"
AUTH_FILE = ROOT / ".dashboard_auth.json"
RECORDS = ROOT / "records.json"
PUSH_LOCK = threading.Lock()
FOLDER_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})-(.+)$")


# ---------- 凭据 / 记录 ----------

def get_auth_token() -> str:
    if not AUTH_FILE.exists():
        AUTH_FILE.write_text(json.dumps({"token": uuid.uuid4().hex[:16]}, indent=1),
                             encoding="utf-8")
    return json.loads(AUTH_FILE.read_text(encoding="utf-8"))["token"]


def add_record(action: str, ok: bool, **kw) -> None:
    recs = []
    if RECORDS.exists():
        try:
            recs = json.loads(RECORDS.read_text(encoding="utf-8"))
        except Exception:
            recs = []
    recs.append({"at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                 "action": action, "ok": ok, **kw})
    RECORDS.write_text(json.dumps(recs[-200:], ensure_ascii=False, indent=1), encoding="utf-8")


def get_records() -> list[dict]:
    if not RECORDS.exists():
        return []
    try:
        return list(reversed(json.loads(RECORDS.read_text(encoding="utf-8"))[-100:]))
    except Exception:
        return []


def load_log() -> dict:
    if PUSH_LOG.exists():
        try:
            return json.loads(PUSH_LOG.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_log(log: dict) -> None:
    PUSH_LOG.write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")


# ---------- 业务 ----------

def list_articles() -> list[dict]:
    log = load_log()
    out = []
    if not ARTICLES.exists():
        return out
    for folder in ARTICLES.iterdir():
        m = FOLDER_RE.match(folder.name)
        if not folder.is_dir() or not m or not (folder / "article.md").exists():
            continue
        text = (folder / "article.md").read_text(encoding="utf-8")
        title = m.group(2)
        hm = re.search(r"^#\s+(.+)", text, re.M)
        if hm:
            title = hm.group(1).strip()
        pushed = log.get(folder.name)
        out.append({
            "dir": folder.name,
            "date": m.group(1),
            "title": title,
            "digest": publish_wechat.extract_meta(text)[1],
            "figs": len(list(folder.glob("fig*.png"))),
            "has_cover": (folder / "cover.png").exists(),
            "pushed": bool(pushed),
            "pushed_at": pushed.get("at", "") if pushed else "",
        })
    out.sort(key=lambda a: a["date"], reverse=True)
    return out


def api_status() -> dict:
    st = {"ip": "?", "token": "?", "drafts": "?"}
    try:
        with urllib.request.urlopen("https://myip.ipip.net/json", timeout=6) as r:
            d = json.loads(r.read().decode("utf-8"))
            st["ip"] = d.get("data", {}).get("ip", "?")
            st["ip_loc"] = " ".join(d.get("data", {}).get("location", [])[:3])
    except Exception:
        st["ip"] = "获取失败"
    try:
        c = json.loads((ROOT / ".wechat_token.json").read_text(encoding="utf-8"))
        ok = time.time() < c.get("expires_at", 0) - 120
        st["token"] = "有效" if ok else "已过期(推送时自动续期)"
        if ok:
            with urllib.request.urlopen(
                "https://api.weixin.qq.com/cgi-bin/draft/count?access_token="
                + c["token"], timeout=8) as r:
                st["drafts"] = json.loads(r.read().decode("utf-8")).get("total_count", "?")
    except Exception:
        st["drafts"] = "查询失败"
    return st


def do_push(dir_name: str) -> dict:
    with PUSH_LOCK:
        r = publish_wechat.push(ARTICLES / dir_name)
        log = load_log()
        log[dir_name] = {"media_id": r["media_id"], "at": datetime.now().strftime("%Y-%m-%d %H:%M")}
        save_log(log)
        return r


def safe_title(t: str) -> str:
    return re.sub(r'[\\/:*?"<>|\s]+', "", t)[:40] or "未命名"


def unique_dir(base: pathlib.Path) -> pathlib.Path:
    if not base.exists():
        return base
    for i in range(2, 99):
        cand = base.with_name(f"{base.name}-{i}")
        if not cand.exists():
            return cand
    raise RuntimeError("目录名冲突过多")


def do_submit(data: dict, actor: str) -> dict:
    """接收一篇完整文章（markdown + base64 配图），落盘到 articles/，可选直接推送。"""
    title = (data.get("title") or "").strip()
    markdown = (data.get("markdown") or "").strip()
    cover_b64 = data.get("cover_b64") or ""
    figs = data.get("figs") or []
    if not title or not markdown or not cover_b64:
        raise RuntimeError("title / markdown / cover_b64 三项都必填")

    date = data.get("date") or datetime.now().strftime("%Y-%m-%d")
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date):
        raise RuntimeError("date 需为 YYYY-MM-DD")

    d = unique_dir(ARTICLES / f"{date}-{safe_title(title)}")
    d.mkdir(parents=True)

    if not re.match(r"^#\s+", markdown):
        markdown = f"# {title}\n\n{markdown}"
    (d / "article.md").write_text(markdown, encoding="utf-8")

    def write_b64(b64: str, path: pathlib.Path):
        try:
            path.write_bytes(base64.b64decode(b64))
        except Exception:
            raise RuntimeError(f"{path.name} 的 base64 解码失败")

    write_b64(cover_b64, d / "cover.png")
    for f in figs:
        name = pathlib.Path(f.get("name") or "fig.png").name
        if not re.match(r"^fig[\w.-]*\.(png|jpe?g|gif|webp)$", name, re.I):
            raise RuntimeError(f"配图文件名不规范: {name}（需 fig*.png 形式）")
        write_b64(f.get("b64") or "", d / name)

    result = {"dir": d.name, "title": title, "figs": len(figs)}
    if data.get("push"):
        r = do_push(d.name)
        result["pushed"] = True
        result["media_id"] = r["media_id"]
    add_record("submit", True, actor=actor, agent=data.get("agent", ""),
               dir=d.name, title=title, pushed=bool(data.get("push")))
    return result


def api_drafts() -> dict:
    """读微信草稿箱列表（标题+更新时间）。"""
    cfg = publish_wechat.load_cfg()
    token = publish_wechat.get_token(cfg)
    req = urllib.request.Request(
        "https://api.weixin.qq.com/cgi-bin/draft/batchget?access_token=" + token,
        data=json.dumps({"offset": 0, "count": 5}).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=15) as r:
        d = json.loads(r.read().decode("utf-8"))
    if d.get("errcode"):
        return {"error": f"{d['errcode']}: {d.get('errmsg', '')}"}
    items = []
    for it in d.get("item", []):
        news = (it.get("content") or {}).get("news_item") or [{}]
        items.append({"title": news[0].get("title", ""),
                      "update": datetime.fromtimestamp(it.get("update_time", 0)).strftime("%m-%d %H:%M")})
    return {"total": d.get("total_count", len(items)), "items": items}


def do_add_topic(topic: str, note: str, agent: str) -> dict:
    """向选题池追加一行（状态 ✍️）；选题与池中已有内容撞车则拒绝。"""
    f = ROOT / "topics" / "backlog.md"
    text = (f.read_text(encoding="utf-8") if f.exists()
            else "# 选题池\n\n| 日期 | 选题 | 状态 | 备注 |\n|------|------|------|------|\n")
    norm = re.sub(r"\s+", "", topic)
    if norm:
        for line in text.splitlines():
            if norm in re.sub(r"\s+", "", line):
                raise RuntimeError(f"选题池已有相似选题（撞车）：{line.strip()[:60]}")
    remark = note or (f"agent提交（{agent}）" if agent else "agent提交")
    text = text.rstrip("\n") + f"\n| {datetime.now().strftime('%Y-%m-%d')} | {topic} | ✍️ | {remark} |\n"
    f.parent.mkdir(exist_ok=True)
    f.write_text(text, encoding="utf-8")
    add_record("topic", True, actor="api", agent=agent, title=topic)
    return {"ok": True, "topic": topic, "status": "✍️"}


def do_build(actor: str) -> dict:
    import build_site
    build_site.build()
    add_record("build", True, actor=actor)
    return {"ok": True, "articles": len(list_articles())}


# ---------- 页面 ----------

PAGE = r"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>公众号发布中枢</title>
<style>
:root{--acc:#3b5bfd;--ink:#171a21;--muted:#8a8f99;--line:#e6e8ef;--bg:#f4f5f9;--ok:#0aa06e;--err:#b3261e}
*{box-sizing:border-box}
body{margin:0;font-family:-apple-system,BlinkMacSystemFont,'PingFang SC','Microsoft YaHei',sans-serif;background:var(--bg);color:#3f3f46;font-size:15px}
header{position:sticky;top:0;z-index:9;background:rgba(255,255,255,.92);backdrop-filter:blur(8px);border-bottom:1px solid var(--line)}
.hi{max-width:980px;margin:0 auto;padding:0 18px;height:58px;display:flex;align-items:center;justify-content:space-between;gap:10px}
.brand{display:flex;align-items:center;gap:9px;font-weight:700;color:var(--ink);font-size:16.5px}
.dot{width:26px;height:26px;border-radius:8px;background:linear-gradient(135deg,#3b5bfd,#7a3bfd);color:#fff;font-size:11px;font-weight:800;display:flex;align-items:center;justify-content:center}
.chips{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
.chip{font-size:12px;color:var(--muted);background:#fff;border:1px solid var(--line);border-radius:999px;padding:3px 11px}
.chip b{color:var(--ink);font-weight:600}
main{max-width:980px;margin:0 auto;padding:22px 18px 70px}
.bar{display:flex;align-items:center;justify-content:space-between;gap:12px;margin:6px 0 18px;flex-wrap:wrap}
.bar h1{margin:0;font-size:20px;color:var(--ink)}
.tabs{display:flex;gap:8px}
.tab{border:1px solid var(--line);background:#fff;border-radius:999px;padding:7px 16px;font-size:13.5px;font-weight:600;color:var(--muted);cursor:pointer}
.tab.on{background:var(--acc);border-color:var(--acc);color:#fff}
.btn{border:none;cursor:pointer;border-radius:999px;padding:9px 18px;font-size:13.5px;font-weight:600;background:var(--acc);color:#fff;transition:.15s}
.btn:hover{background:#2f4be0}
.btn.ghost{background:#fff;color:var(--acc);border:1px solid var(--acc)}
.btn.small{padding:7px 14px;font-size:12.5px}
.btn:disabled{opacity:.5;cursor:wait}
.cards{display:flex;flex-direction:column;gap:14px}
.card{background:#fff;border:1px solid var(--line);border-radius:13px;padding:16px 18px;display:flex;gap:14px;align-items:flex-start}
.date{flex:0 0 96px;text-align:center;background:#eef1ff;border-radius:10px;padding:9px 4px}
.date b{display:block;font-size:21px;color:var(--acc);line-height:1.1}
.date span{font-size:11.5px;color:var(--muted)}
.info{flex:1;min-width:0}
.info h3{margin:0 0 6px;font-size:16px;color:var(--ink);line-height:1.5}
.info .digest{margin:0 0 8px;font-size:13px;color:var(--muted);display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.meta{font-size:12px;color:var(--muted)}
.meta .ok{color:var(--ok);font-weight:600}
.acts{flex:0 0 auto;display:flex;flex-direction:column;gap:8px}
table{width:100%;border-collapse:collapse;background:#fff;border:1px solid var(--line);border-radius:12px;overflow:hidden}
th{background:#eef1ff;color:var(--ink);font-size:12.5px;padding:9px 12px;text-align:left}
td{font-size:13px;padding:9px 12px;border-top:1px solid var(--line);color:#3f3f46;vertical-align:top}
.tag{display:inline-block;padding:2px 9px;border-radius:999px;font-size:11.5px;font-weight:600}
.tag.push{background:#e8f0ff;color:#3b5bfd}.tag.submit{background:#e6f7f0;color:#0aa06e}
.tag.build{background:#f4ecff;color:#7a3bfd}.tag.err{background:#fdecea;color:#b3261e}
.toast{position:fixed;left:50%;transform:translateX(-50%);bottom:26px;background:#171a21;color:#fff;font-size:13.5px;border-radius:10px;padding:11px 20px;max-width:86vw;box-shadow:0 10px 30px rgba(0,0,0,.25);opacity:0;transition:.25s;pointer-events:none;z-index:99}
.toast.show{opacity:1}
.toast.ok{background:#0b7a55}.toast.err{background:#b3261e}
.note{margin-top:26px;font-size:12.5px;color:var(--muted);line-height:1.9;background:#fff;border:1px dashed var(--line);border-radius:10px;padding:12px 16px}
.note code{background:#f0f2f8;border-radius:4px;padding:1px 6px;font-size:12px}
@media(max-width:640px){.card{flex-wrap:wrap}.acts{flex-direction:row;width:100%}.acts .btn{flex:1}.date{flex:0 0 84px}th:nth-child(4),td:nth-child(4){display:none}}
</style></head><body>
<header><div class="hi">
  <div class="brand"><span class="dot">发</span>公众号发布中枢</div>
  <div class="chips">
    <span class="chip">出口IP <b id="ip">…</b></span>
    <span class="chip">token <b id="tk">…</b></span>
    <span class="chip">草稿箱 <b id="dr">…</b></span>
    <button class="chip" style="cursor:pointer" onclick="setKey()" title="设置 API Token">🔑</button>
  </div>
</div></header>
<main>
  <div class="bar">
    <h1 id="pageTitle">待发文章</h1>
    <div style="display:flex;gap:10px;align-items:center">
      <div class="tabs">
        <div class="tab on" id="tabA" onclick="switchTab('A')">文章</div>
        <div class="tab" id="tabR" onclick="switchTab('R')">操作记录</div>
      </div>
      <button class="btn ghost small" onclick="refresh()">刷新</button>
      <button class="btn ghost small" onclick="buildSite(this)">重建网站</button>
    </div>
  </div>
  <div id="viewA"><div class="cards" id="list"></div></div>
  <div id="viewR" style="display:none"></div>
  <div class="note">
    <b>说明</b>：本页面即发布中枢，局域网内 agent 可通过 <code>POST /api/submit</code> 提交文章并直接推送（请求头 <code>X-Auth</code>，
    Token 首次启动时打印在服务端控制台，也可点右上角 🔑 设置）。每次提交/推送/构建都会记录在「操作记录」里（落盘 records.json）。<br>
    推送后仍需人工在手机「公众平台助手」小程序确认发布；推送时本机 VPN 需保持关闭。
  </div>
</main>
<div class="toast" id="toast"></div>
<script>
function toast(msg,cls){var t=document.getElementById('toast');t.textContent=msg;t.className='toast show '+(cls||'');clearTimeout(t._h);t._h=setTimeout(function(){t.className='toast'},4200);}
function esc(s){return String(s).replace(/[&<>"]/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]})}
function authHeader(){var k=localStorage.getItem('gzh_key');return k?{'X-Auth':k}:{}}
function setKey(){var k=prompt('API Token（服务端控制台首次启动时打印）:',localStorage.getItem('gzh_key')||'');if(k!==null)localStorage.setItem('gzh_key',k.trim());}
function post(url,body){return fetch(url,{method:'POST',headers:Object.assign({'Content-Type':'application/json'},authHeader()),body:JSON.stringify(body||{})})
 .then(function(r){return r.json().then(function(j){if(r.status===401){setKey();throw new Error('Token 缺失或不对，已弹窗让你填写');}return {ok:r.ok,j:j}})})}
function render(list){
  var el=document.getElementById('list');
  if(!list.length){el.innerHTML='<div style="text-align:center;color:var(--muted);padding:40px">articles/ 下还没有文章</div>';return}
  el.innerHTML=list.map(function(a){
    var d=a.date.split('-');
    return '<div class="card">'
      +'<div class="date"><b>'+parseInt(d[2],10)+'</b><span>'+parseInt(d[1],10)+'月</span></div>'
      +'<div class="info"><h3>'+esc(a.title)+'</h3><p class="digest">'+esc(a.digest)+'</p>'
      +'<div class="meta">'+a.figs+' 张配图 · 封面'+(a.has_cover?'√':'缺！')+(a.pushed?' · <span class="ok">已推送 '+esc(a.pushed_at)+'</span>':'')+'</div></div>'
      +'<div class="acts">'
      +'<button class="btn ghost small" onclick="window.open(\'/preview/'+encodeURIComponent(a.dir)+'/article.html\')">预览排版</button>'
      +'<button class="btn small" onclick="pushArt(this,\''+encodeURIComponent(a.dir)+'\')">'+(a.pushed?'再推一次':'推送草稿')+'</button>'
      +'</div></div>';
  }).join('');
}
function renderRecords(rs){
  var el=document.getElementById('viewR');
  if(!rs.length){el.innerHTML='<div style="text-align:center;color:var(--muted);padding:40px">还没有记录</div>';return}
  el.innerHTML='<table><tr><th>时间</th><th>操作</th><th>文章 / 结果</th><th>来源</th></tr>'
   +rs.map(function(r){
     var main=esc(r.title||r.dir||''), sub=r.ok?'':'<span style="color:var(--err)">'+esc(r.error||'失败')+'</span>';
     if(r.media_id)sub=(sub?sub+' ':'')+'<span style="color:var(--muted);font-size:11px">'+esc(r.media_id.slice(0,18))+'…</span>';
     return '<tr><td style="white-space:nowrap">'+esc(r.at)+'</td>'
      +'<td><span class="tag '+(r.ok?esc(r.action):'err')+'">'+esc(r.action)+'</span></td>'
      +'<td>'+main+' '+sub+'</td>'
      +'<td style="font-size:12px;color:var(--muted)">'+esc(r.agent||r.actor||'')+'</td></tr>';
   }).join('')+'</table>';
}
function refresh(){
  fetch('/api/articles').then(function(r){return r.json()}).then(render).catch(function(e){toast('加载失败 '+e,'err')});
  fetch('/api/records').then(function(r){return r.json()}).then(renderRecords).catch(function(){});
}
function switchTab(t){
  document.getElementById('viewA').style.display=t==='A'?'':'none';
  document.getElementById('viewR').style.display=t==='R'?'':'none';
  document.getElementById('tabA').className='tab'+(t==='A'?' on':'');
  document.getElementById('tabR').className='tab'+(t==='R'?' on':'');
  document.getElementById('pageTitle').textContent=t==='A'?'待发文章':'操作记录';
}
function pushArt(btn,dir){
  var old=btn.textContent;btn.disabled=true;btn.textContent='推送中…';
  post('/api/push',{dir:decodeURIComponent(dir)})
   .then(function(res){
     if(res.ok){toast('《'+res.j.title+'》已进草稿箱 → 手机上预览后点发布','ok');addPushRecordLocal(dir);}
     else toast('推送失败：'+(res.j.error||'未知错误'),'err');
     refresh();
   }).catch(function(e){toast(String(e),'err');btn.disabled=false;btn.textContent=old});
}
function addPushRecordLocal(dir){/* 记录由服务端写，这里仅触发刷新 */}
function buildSite(btn){
  btn.disabled=true;btn.textContent='构建中…';
  post('/api/build',{})
   .then(function(res){toast(res.ok?'网站已重建':'构建失败：'+(res.j.error||''),'ok');btn.disabled=false;btn.textContent='重建网站';refresh()})
   .catch(function(e){toast(String(e),'err');btn.disabled=false;btn.textContent='重建网站'});
}
fetch('/api/status').then(function(r){return r.json()}).then(function(s){
  document.getElementById('ip').textContent=(s.ip==='获取失败'?'获取失败':s.ip)+(s.ip_loc?'（'+s.ip_loc+'）':'');
  document.getElementById('tk').textContent=s.token;
  document.getElementById('dr').textContent=s.drafts;
});
refresh();
</script></body></html>"""


def esc(s, quote: bool = False) -> str:
    return html.escape(s, quote=quote)


def mcp_page_html() -> str:
    """生成 /mcp 工具一览页（数据直接取自 mcp_server.TOOLS，永远与实际一致）。"""
    import mcp_server as ms

    cards = []
    for t in ms.TOOLS:
        props = t["inputSchema"].get("properties", {})
        required = set(t["inputSchema"].get("required", []))
        rows = "".join(
            f'<tr><td class="k">{esc(k)}</td><td>{esc(str(v.get("type", "")))}</td>'
            f'<td>{"<b>必填</b>" if k in required else "可选"}</td>'
            f'<td class="d">{esc(str(v.get("description", "")))}</td></tr>'
            for k, v in props.items())
        params = (f'<table><tr><th>参数</th><th>类型</th><th></th><th>说明</th></tr>{rows}</table>'
                  if props else '<p class="none">（无参数）</p>')
        cards.append(f'<div class="tool"><h3>{esc(t["name"])}</h3>'
                     f'<p class="desc">{esc(t["description"])}</p>{params}</div>')

    return f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>MCP 工具一览 · 公众号发布中枢</title>
<style>
:root{{--acc:#3b5bfd;--ink:#171a21;--muted:#8a8f99;--line:#e6e8ef;--bg:#f4f5f9}}
*{{box-sizing:border-box}}
body{{margin:0;font-family:-apple-system,BlinkMacSystemFont,'PingFang SC','Microsoft YaHei',sans-serif;background:var(--bg);color:#3f3f46;font-size:15px}}
header{{background:linear-gradient(135deg,#0c1130,#1c2757);color:#fff;padding:30px 0 26px}}
.hi{{max-width:860px;margin:0 auto;padding:0 20px}}
header h1{{margin:0 0 6px;font-size:22px}}
header p{{margin:0;color:#aab6e8;font-size:13.5px}}
main{{max-width:860px;margin:0 auto;padding:24px 20px 60px}}
.tool{{background:#fff;border:1px solid var(--line);border-radius:13px;padding:18px 20px;margin-bottom:14px}}
.tool h3{{margin:0 0 8px;font-size:16.5px;color:var(--ink);font-family:Consolas,monospace}}
.tool .desc{{margin:0 0 10px;font-size:13.5px;line-height:1.8}}
table{{border-collapse:collapse;width:100%}}
th{{text-align:left;font-size:12px;color:var(--muted);padding:5px 10px;border-bottom:1px solid var(--line)}}
td{{font-size:13px;padding:6px 10px;border-bottom:1px solid #f0f2f6;vertical-align:top}}
td.k{{font-family:Consolas,monospace;color:var(--acc)}}
td.d{{color:var(--muted);font-size:12.5px}}
.none{{color:var(--muted);font-size:13px;margin:0}}
.how{{background:#fff;border:1px dashed var(--line);border-radius:12px;padding:16px 18px;font-size:13px;color:var(--muted);line-height:1.9}}
.how code{{background:#f0f2f8;border-radius:4px;padding:1px 6px;font-size:12px}}
b{{color:#0aa06e}}
</style></head><body>
<header><div class="hi">
<h1>MCP 工具一览（{len(ms.TOOLS)} 个）</h1>
<p>公众号发布中枢 · 数据实时取自 mcp_server.py，与实际可用工具始终一致</p>
</div></header>
<main>
{''.join(cards)}
<div class="how">
<b>接入方式一（HTTP，推荐外部 agent）</b>：MCP 客户端直接连 <code>POST /mcp</code>（Streamable HTTP 传输），
鉴权头 <code>Authorization: Bearer &lt;token&gt;</code>（或 <code>X-Auth</code>）。<br>
<b>接入方式二（stdio）</b>：配置 <code>command: python tools/mcp_server.py</code>，
env 给 <code>HUB_URL</code>（本页地址）与 <code>HUB_TOKEN</code>；中枢机器上 Token 自动读取。<br>
<b>机器可读清单</b>：<code>GET /tools?format=json</code> 返回全部工具的 name / description / inputSchema。<br>
<b>自检</b>：<code>python tools/mcp_client_test.py</code>（stdio 全量）或
<code>MCP_TRANSPORT=http python tools/mcp_client_test.py</code>（HTTP 端点）。
</div>
</main></body></html>"""


# ---------- HTTP ----------

class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "GzhHub/2.0"

    def log_message(self, fmt, *args):
        pass

    @property
    def actor(self) -> str:
        return self.client_address[0]

    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _check_auth(self) -> bool:
        return self.headers.get("X-Auth", "") == get_auth_token()

    def _mcp_http_post(self):
        """MCP Streamable HTTP 端点：POST JSON-RPC -> JSON 响应（本服务无服务端主动推送，GET/DELETE 返回 405）。"""
        auth = self.headers.get("Authorization", "")
        bearer = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
        token = get_auth_token()
        if bearer != token and self.headers.get("X-Auth", "") != token:
            return self._json({"jsonrpc": "2.0", "id": None,
                               "error": {"code": -32001,
                                         "message": "缺少或错误 Token（Authorization: Bearer <token> 或 X-Auth 头）"}}, 401)
        try:
            msg = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))).decode("utf-8"))
        except Exception as e:
            return self._json({"jsonrpc": "2.0", "id": None,
                               "error": {"code": -32700, "message": f"parse error: {e}"}}, 400)
        import mcp_server
        resp = mcp_server.handle(msg)
        if resp is None:  # notification：按 MCP 规范 202 即可
            self.send_response(202)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        body = json.dumps(resp, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        """浏览器类 MCP 客户端的 CORS 预检。"""
        self.send_response(204)
        for k, v in {"Access-Control-Allow-Origin": "*",
                     "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
                     "Access-Control-Allow-Headers":
                         "Content-Type, Authorization, X-Auth, Mcp-Session-Id, Last-Event-ID"}.items():
            self.send_header(k, v)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        if u.path in ("/", "/index.html"):
            body = PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif u.path == "/api/articles":
            self._json(list_articles())
        elif u.path == "/api/status":
            self._json(api_status())
        elif u.path == "/api/records":
            self._json(get_records())
        elif u.path == "/api/backlog":
            f = ROOT / "topics" / "backlog.md"
            self._json({"content": f.read_text(encoding="utf-8") if f.exists() else ""})
        elif u.path == "/api/article":
            qs = urllib.parse.parse_qs(u.query)
            d = (qs.get("dir") or [""])[0]
            f = (ARTICLES / d).resolve()
            if not d or not str(f).startswith(str(ARTICLES.resolve())) or not (f / "article.md").is_file():
                return self._json({"error": "文章不存在"}, 404)
            self._json({"dir": d, "markdown": (f / "article.md").read_text(encoding="utf-8")})
        elif u.path == "/api/drafts":
            self._json(api_drafts())
        elif u.path == "/mcp":
            # MCP Streamable HTTP 端点只接受 POST；GET 按 MCP 规范返回 405
            self.send_response(405)
            self.send_header("Allow", "POST, OPTIONS")
            self.send_header("Content-Length", "0")
            self.end_headers()
        elif u.path in ("/tools", "/tools/"):
            if urllib.parse.parse_qs(u.query).get("format", [""])[0] == "json":
                import mcp_server as ms
                return self._json({"tools": [{"name": t["name"],
                                              "description": t["description"],
                                              "inputSchema": t["inputSchema"]}
                                             for t in ms.TOOLS]})
            body = mcp_page_html().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif u.path.startswith("/preview/"):
            self._serve_preview(u.path[len("/preview/"):])
        else:
            self.send_error(404)

    def _serve_preview(self, rel: str):
        base = ARTICLES.resolve()
        target = (base / urllib.parse.unquote(rel)).resolve()
        if not str(target).startswith(str(base)) or not target.is_file():
            self.send_error(404)
            return
        body = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type",
                         mimetypes.guess_type(target.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> dict:
        try:
            return json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0)))
                              .decode("utf-8"))
        except Exception:
            return {}

    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        if u.path == "/mcp":
            return self._mcp_http_post()
        if u.path not in ("/api/push", "/api/submit", "/api/build", "/api/backlog"):
            return self.send_error(404)
        if not self._check_auth():
            add_record("auth-fail", False, actor=self.actor, action_hint=u.path)
            return self._json({"error": "缺少或错误的 X-Auth Token（见服务端控制台）"}, 401)
        data = self._body()
        try:
            if u.path == "/api/push":
                if not data.get("dir"):
                    return self._json({"error": "缺少 dir 参数"}, 400)
                r = do_push(data["dir"])
                add_record("push", True, actor=self.actor, agent=data.get("agent", ""),
                           dir=data["dir"], title=r["title"], media_id=r["media_id"])
                print(f"[中枢] 推送成功 {data['dir']} (来自 {self.actor})")
                return self._json(r)
            if u.path == "/api/submit":
                r = do_submit(data, self.actor)
                print(f"[中枢] 收到提交 {r['dir']} (来自 {self.actor})")
                return self._json(r)
            if u.path == "/api/backlog":
                topic = (data.get("topic") or "").strip()
                if not topic:
                    return self._json({"error": "缺少 topic 参数"}, 400)
                r = do_add_topic(topic, data.get("note", ""), data.get("agent", ""))
                print(f"[中枢] 新选题登记: {topic} (来自 {self.actor})")
                return self._json(r)
            if u.path == "/api/build":
                return self._json(do_build(self.actor))
        except SystemExit as e:
            add_record(u.path.strip("/api/"), False, actor=self.actor,
                       dir=data.get("dir", ""), error=str(e))
            return self._json({"error": str(e)}, 500)
        except Exception as e:
            add_record(u.path.strip("/api/"), False, actor=self.actor,
                       dir=data.get("dir", ""), error=f"{type(e).__name__}: {e}")
            return self._json({"error": f"{type(e).__name__}: {e}"}, 500)


def lan_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("192.168.1.1", 1))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    port = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 8741
    # /mcp 端点内嵌的 mcp_server 调中枢 API 时走本机回环
    os.environ.setdefault("HUB_URL", f"http://127.0.0.1:{port}")
    token = get_auth_token()
    httpd = http.server.ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print("=" * 56)
    print(f"  公众号发布中枢已启动")
    print(f"  本机使用 : http://127.0.0.1:{port}/")
    print(f"  局域网   : http://{lan_ip()}:{port}/")
    print(f"  API Token: {token}   （写接口请求头 X-Auth）")
    print(f"  首次局域网访问如被防火墙拦截，允许 Python 专用/专用网络即可")
    print("=" * 56)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n已退出")


if __name__ == "__main__":
    main()

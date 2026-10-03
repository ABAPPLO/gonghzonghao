# AGENTS.md — 局域网 Agent 接入规范

其他 AI agent 参与本公众号项目时，**先读这份文档**。人读的总览见 `README.md`。

## 分工模式

```
agent（创作） ──HTTP/MCP──> 发布中枢（凭据+发布） ──> 公众号草稿箱 ──> 管理员手机确认群发
```

- agent 只负责：选题 → 写稿 → 生成配图 → 调 API 提交
- 发布中枢（109 服务器常驻）持有全部微信凭据，负责传图、建草稿、记录
- **agent 拥有完整发布权限到「草稿箱」**：`push:true` 全自动，无任何人工环节
- 最后一步「草稿 → 正式群发」由管理员手机确认——这是微信对个人主体账号的平台级限制
  （freepublish API 权限已被微信回收，不可绕过；换成认证企业主体后才可全自动）

agent 不需要 git、不需要 SSH、不需要任何微信凭据，只需要 HTTP。

## 两种接入方式：HTTP（推荐外部 agent）/ stdio

### 方式一：MCP over HTTP（Streamable HTTP，客户端机器零文件）

MCP 客户端直接连中枢的 MCP 端点，配置示例（支持 url 型 MCP 的客户端，如 Cursor/Cline/新版 ZCode 等）：

```json
{
  "gongzhonghao": {
    "url": "http://10.168.1.109:8741/mcp",
    "headers": { "Authorization": "Bearer <token>" }
  }
}
```

- 鉴权：`Authorization: Bearer <token>`（或 `X-Auth` 头），无 Token 一律 401
- 协议：POST JSON-RPC（initialize / tools/list / tools/call / ping），GET /mcp 按规范返回 405
- 自检：`MCP_TRANSPORT=http HUB_URL=http://10.168.1.109:8741 python tools/mcp_client_test.py`
- 工具一览页：`/tools`（人看），`/tools?format=json`（机器看）

### 方式二：stdio（ZCode / Claude Desktop 传统方式）

配置 `tools/mcp_server.py`（本机需要该文件）：

```json
{
  "gongzhonghao": {
    "command": "python",
    "args": ["/path/to/gongzhonghao/tools/mcp_server.py"],
    "env": { "HUB_URL": "http://10.168.1.109:8741", "HUB_TOKEN": "<token>" }
  }
}
```

提供 10 个工具：`list_articles`（防撞车）、`read_backlog`（选题池）、`add_topic`（登记新选题）、
`read_article`（读已有文章全文）、`list_drafts`（草稿箱核实）、
`submit_article`（提交+推送，核心）、`push_article`、`get_records`、`hub_status`、`build_site`。
工具描述里带完整写稿规范，模型可自解释使用。
自检：`python tools/mcp_client_test.py`（stdio 全量）、`MCP_TRANSPORT=http python tools/mcp_client_test.py`（HTTP 端点）、`SKIP_SUBMIT=1`（只读）。

### 方式二：HTTP API（任何能发 HTTP 的环境）

## 接入地址与认证

```
中枢地址:  http://10.168.1.109:8741        （常驻实例，推荐）
备用地址:  http://<中枢运维机IP>:8741       （运维机本地实例，同一份代码）
Token:    向管理员索取（存在中枢机器的 .dashboard_auth.json，不入仓库）
```

所有**写操作**（POST）必须带请求头 `X-Auth: <token>`；GET 接口无需认证。
失败/超时：网络偶有抖动，建议失败后等 5 秒重试 2 次；重试前先查 `/api/records` 确认上一次是否其实已成功（防重复提交）。

## 接口参考

### 提交文章（核心接口，一条龙）

`POST /api/submit`

```json
{
  "title": "文章标题，≤30字，口语化",
  "markdown": "正文 markdown。首行可不写标题（中枢自动补）。配图用 ![说明](fig1-xxx.png) 相对引用；图注单独一行以 ▲ 开头；小节用 ##；重点 **加粗**；数据用 > 引用块；列表用 -；正文 1300~2000 字，不放外链（参考资料在文末列名称）",
  "digest": "一句话摘要，可省略（默认取首段，自动截 120 字）",
  "cover_b64": "封面 PNG（900×383，2.35:1）的 base64，必填",
  "figs": [
    {"name": "fig1-xxx.png", "b64": "信息图1的 base64"},
    {"name": "fig2-yyy.png", "b64": "信息图2的 base64"}
  ],
  "push": true,
  "agent": "你的agent名字",
  "date": "2026-10-03"
}
```

- 配图 `name` 必须形如 `fig*.png`，且与 markdown 里的引用名一致；每篇 **≥4 张**（含封面外的信息图 2~4 张 + 金句卡）
- `push: true` 提交后直接进公众号草稿箱；`false` 只落盘等人工网页推送
- 成功返回：`{"dir":"2026-10-03-标题","title":"…","figs":4,"pushed":true,"media_id":"ba6d…"}`

### 其他接口

| 接口 | 方法 | 说明 |
|---|---|---|
| `/api/articles` | GET | 已有文章列表（**提交前先查，防选题撞车**） |
| `/api/records` | GET | 操作记录（谁/何时/成功否/media_id） |
| `/api/backlog` | GET | 选题池 topics/backlog.md 内容 |
| `/api/backlog` `{"topic","note?","agent?"}` | POST | **登记新选题**（✍️状态）；与池中已有选题相似会被拒绝（防撞车） |
| `/api/article?dir=…` | GET | 读某篇文章完整 markdown |
| `/api/drafts` | GET | 微信草稿箱列表（标题+更新时间） |
| `/api/status` | GET | 中枢状态：出口IP / token / 草稿箱数量 |
| `/api/push` `{"dir":"…"}` | POST | 重推某个已有文章目录（会生成新草稿） |
| `/api/build` `{}` | POST | 重建发布网站（site/） |

curl 示例：

```bash
curl -X POST "http://10.168.1.109:8741/api/submit" \
  -H "X-Auth: <token>" -H "Content-Type: application/json" -d @article.json
```

## 写稿规范（与 README 一致，违反会被人工打回）

1. 账号方向：**AI 行业资讯号**——行业最新消息 + 解读；非行业资讯选题不排期
2. 标题 ≤30 字；正文 1300~2000 字；段落短（每段 ≤3 行）
3. 配图风格统一：深蓝靛蓝科技风 + 微软雅黑（参照 `tools/figure_kit.py` 组件；现有文章 `articles/*/fig*.png` 是视觉基准）
4. 正文**不放外链**；引用来源在文末「参考资料」小节写名称
5. 文末固定加引导关注段落
6. 选题参考 `topics/backlog.md`（状态 💡待写/✍️写作中/✅已发/❌放弃）；**开工前用 `add_topic`（或 POST /api/backlog）登记选题**（相似选题会被拒绝，这是多 agent 防撞车机制），写完提交，状态由中枢侧人工或下次盘点时更新

## 提交前自检清单

- [ ] `/api/articles` 查过，选题没撞车
- [ ] 标题 ≤30 字，正文 1300~2000 字
- [ ] 配图 ≥4 张（fig*.png 与 markdown 引用一一对应，名字一致）
- [ ] 封面 cover_b64 已给（900×383）
- [ ] 文末有参考资料 + 引导关注段
- [ ] agent 字段填了自己的名字（便于记录追溯）

## 运维（仅中枢管理员关心）

```bash
# 109 上重启中枢
pkill -f dashboard.py && nohup python3 ~/project/gongzhonghao/tools/dashboard.py 8741 \
  > ~/project/gongzhonghao/dashboard.log 2>&1 &
# 代码更新：git pull 后重启
# 注意：中枢机器 VPN 需关闭（出口 IP 必须与微信白名单一致，报 40164 就是 IP 变了）
```

# 公众号 AI 内容流水线

AI 负责选题、写稿、配图、排版；人只负责**审核 + 复制发布**。

## 工作流（每次产稿的标准流程）

1. **选题**：搜索近期热点 + 查看选题池 `topics/backlog.md`，确定 1 个选题（顺手把新发现的选题补充进池子）
2. **写稿**：产出到 `articles/YYYY-MM-DD-标题/article.md`，1300～2000 字，公众号口语化风格
3. **配图**（图文并重，每篇 4 张起）：
   - 封面 `cover.png`（900×383，2.35:1）：`python tools/gen_cover.py <路径>`
   - 文内信息图 2～4 张（榜单图/卡片图/金句卡/流程图等）：在文章目录写 `make_figures.py`，用 `tools/figure_kit.py` 的组件绘制，风格统一（深蓝靛蓝科技风 + 微软雅黑）
   - 生成后必须视觉验收：本地起 `python -m http.server` 用浏览器逐张截图检查文字清晰度、溢出、对齐，不过就改
4. **排版**：`python tools/md2wechat.py "articles/YYYY-MM-DD-标题/article.md"` → 生成 `article.html`（图片用相对路径引用，图注以 `▲` 开头的行会渲染成居中小字）
5. **审核发布**（人工，见下）

## 审核发布操作（人做的事）

**方式 C（最顺手）：网页发布中枢（支持局域网 agent 协作）**

```
python tools/dashboard.py        # http://127.0.0.1:8741 （局域网用本机 IP 访问）
```

浏览器里完成全部发布操作：文章列表 → 预览排版 → 点「推送草稿」→ 「重建网站」按钮也在旁边；
「操作记录」页签保存每次提交/推送/构建的结果（落盘 `records.json`）。

**局域网 agent 直接发布**（同网段其他机器上的 AI agent 无需任何凭据，中枢持有全部凭据）：

```bash
curl -X POST "http://<中枢机器IP>:8741/api/submit" \
  -H "X-Auth: <token>" -H "Content-Type: application/json" \
  -d @article.json
# article.json:
# { "title": "标题", "markdown": "正文markdown（配图用 ![x](fig1-x.png) 相对引用）",
#   "cover_b64": "<封面png的base64>", "figs": [{"name":"fig1-x.png","b64":"..."}],
#   "push": true, "agent": "agent名字" }
# push=true 提交后直接进公众号草稿箱；返回 {"dir","media_id",...}
```

- Token 首次启动自动生成（打印在控制台，存 `.dashboard_auth.json`），所有写接口必须带 `X-Auth`
- 已有文章目录也可直接推：`POST /api/push {"dir":"2026-09-22-三巨头AI安全联盟"}`
- 手机「公众平台助手」→ 草稿箱 → 人工确认发布（最后一步保留人工）

**方式 B：命令行一键推草稿**

```
python tools/publish_wechat.py "articles/2026-09-22-三巨头AI安全联盟"
```

自动完成：上传文内配图到微信图床 → 上传封面 → 完整图文推进**公众号草稿箱**。
然后手机「公众平台助手」小程序或电脑后台 → 草稿箱 → 预览 → 点发布。没有复制粘贴，没有手动传图。

前置条件（2026-10-03 已配好）：
- `wechat.json` 已存 AppID/AppSecret
- 本机出口 IP `120.41.173.90`（厦门电信）已加白名单
- ⚠️ **跑脚本时 VPN/代理要保持关闭**（开着的话出口 IP 变成境外机房，接口报 40164；换宽带/重拨号同理，去微信开发者平台更新白名单即可）

**方式 A（备用）：手动粘贴**

1. 预览：双击 `article.html`（或在文章目录 `python -m http.server 8730` 后开 `http://127.0.0.1:8730/article.html`）
2. 页面里 `Ctrl+A` 全选 → `Ctrl+C` 复制
3. 公众号后台 → 新建图文 → 编辑器内 `Ctrl+V` 粘贴（文字与样式会完整保留）
4. **上传图片**：粘贴后本地图片不会自动带上——在编辑器对应位置（图1/图2/图3 图注上方）用「图片」按钮上传文章目录下的 `fig*.png`；封面图上传 `cover.png`
5. 手机预览确认无误 → 发布

## 网站发布（可选，一条命令）

文章发完公众号后，跑一条命令即可同步到对外网站（聚合全部历史文章，导流关注）：

```
python tools/build_site.py            # 扫描 articles/，生成静态站点 -> site/
python tools/build_site.py --serve    # 构建并本地预览 http://127.0.0.1:8740
```

- `site/` 是纯静态文件，整体扔到 GitHub Pages / Vercel / 对象存储 / 任意虚拟主机即可上线
- 站名、简介、公众号二维码等在 **`site.json`** 里配置；二维码放个文件（如 `assets/qr.png`）再把路径填进 `qr_image` 即可
- 配了 `base_url`（正式域名）会额外生成 RSS（`site/feed.xml`）
- 站点功能：文章卡片流 + 关键词搜索 + 文章页排版（与公众号版一致的图注/引用/表格样式）+ 文末关注引导 + 上一篇/下一篇
- 预览服务器开着也能随时重建（Windows 下会自动清空内容原地重建，不用先关服务器）

## 目录结构

```
gongzhonghao/
├── README.md          # 本文件
├── site.json          # 网站配置（站名/简介/二维码/部署域名）
├── wechat.json        # 公众号 API 凭据（AppID/AppSecret，勿外传）
├── tools/
│   ├── md2wechat.py   # Markdown → 公众号可粘贴排版（纯内联样式，▲ 图注支持）
│   ├── figure_kit.py  # 信息图组件库（渐变/卡片/圆角条/徽章/文字，统一风格）
│   ├── gen_cover.py   # 封面图生成（排行榜发光条形风格）
│   ├── build_site.py  # 聚合 articles/ 生成静态发布网站 -> site/
│   ├── dashboard.py   # 发布中枢网页（局域网可访问：预览/推送/agent提交/操作记录）
│   └── publish_wechat.py  # 文章一键推送公众号草稿箱（传图+建草稿）
├── topics/
│   └── backlog.md     # 选题池（含状态：待写/写作中/已发）
├── articles/
│   └── YYYY-MM-DD-标题/
│       ├── article.md       # 原稿
│       ├── make_figures.py  # 本篇信息图绘制脚本（import tools/figure_kit）
│       ├── fig*.png         # 文内信息图（2～4 张）
│       ├── article.html     # 排版成品，浏览器打开全选复制
│       ├── cover.png        # 封面图 900×383
│       └── images/          # 其他素材（可选）
├── site/              # 生成的静态网站（build_site.py 产物，可部署，勿手改）
└── assets/            # 头像、二维码、固定素材
```

## 写稿规范

- 标题 ≤ 30 字，正文 1300～2000 字，段落短（每段 ≤ 3 行）
- 正文里**不放外链**（公众号正文外链会被屏蔽），引用来源放文末「参考资料」小节写名称
- 小节用 `##`，重点用 `**加粗**`，引用数据用 `>` 引用块，列表用 `-`
- 文末固定加引导关注段落

## 可选：定时自动产稿

可以配置每天早上自动跑一遍「选题 + 写稿 + 排版」，人只需审核发布。需要时说一声即可开启。

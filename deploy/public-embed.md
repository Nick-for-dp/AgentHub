# 208 公网嵌入上线 Runbook（agent.zjmi56.com，ADR-022，网关 TLS 卸载形态）

目标：208 开通公网入口，产业互联网（博采，HTTPS）iframe 嵌入营销智能体。
形态：**公司网关做 TLS 卸载**——证书挂网关，公网 443 解密后明文转发 208:80；
208 不开 443、不管证书。管理后台在 81 端口（仅内网），与公网面端口级隔离。
原则：全部 Nginx/配置层完成，不改应用代码。

## 0. 前置条件（逐项确认后再动手）

| # | 项 | 确认方式 | 状态（2026-08-20） |
|---|---|---|---|
| 1 | 网关映射 **公网IP:443 → 208:80**（TLS 卸载，公网 80→443 重定向由网关负责），仅此一条公网通路 | 网络组回执 | ✅ 已开通 |
| 2 | DNS A 记录 `agent.zjmi56.com` → 公网 IP | `nslookup agent.zjmi56.com` | ✅ 已开通 |
| 3 | 证书挂在网关上（非我方职责），续期责任人明确 | 网络组 | ⏳ 待书面确认 |
| 4 | 网关转发**保留原始 Host: agent.zjmi56.com**（安全命门：改写则 Host 分流失效，仅剩端口隔离兜底） | 网络组回执 + 第 6 节实测 | ✅ 已确认 |
| 5 | 网关带 X-Forwarded-For（多层链，不可可靠还原真实来源 → 全链记日志，限流只做粗粒度防洪） | 网络组回执 | ✅ 已确认 |
| 6 | 网关不缓冲 SSE/chunked、长连接空闲超时 ≥10 分钟 | 联调专项实测（第 5.3 节） | 🟡 口头支持，实测兜底 |
| 7 | 网关单请求体上限 ≥20MB（语音上传 15MB） | 网络组回执 | ✅ 已确认（>20MB） |
| 8 | **81 端口永不映射公网**（管理面端口隔离的前提） | 网络组回执 | ⏳ 待书面确认 |
| 9 | 博采生产父页面 origin + 联调页面 origin（`协议://主机[:端口]`，逐字，无路径无尾斜杠） | 博采对接人 | ⏳ 待提供 |
| 10 | embed token 参数对齐：`iss=industrial-internet`、`aud=agenthub`、HS256 共享密钥（我方生成，安全渠道送达博采后端） | `docs/20260617对接文档.md` §7 | ⏳ 待对齐 |
| 11 | 博采开发出口 IP：`39.183.172.64`（联调白名单用） | 博采对接人 | ✅ 已提供 |
| 12 | 联调白名单在**网关边缘**做源 IP ACL（208 拿不到可靠真实来源，无法在本地做） | 网络组 | ⏳ 待回执；做不了则见第 8 节兜底 |

> **分阶段阻塞口径（2026-08-20 定）**：1–8 为部署与开口前提（其中 3/8/12 可并行催办、
> 不阻塞内网基线）；9–12 **只阻塞第 5 节联调**，可在部署完成后再对齐。
> 注意补做成本不对称：后端 origin/密钥改 `.env` + 重启即可；前端 origin 是
> **构建期注入**，补做 = 改 `frontend/.env` 重新 `npm run build` 替换 dist。
> 密钥建议部署时就生成配好（将来直接发博采，零补做）。

## 1. 前端构建（嵌入页校验父页面 origin 是构建期注入）

在 208 上构建（本次部署形态）。**首次基线部署可不带 origin 直接构建**（嵌入页暂不
工作，客户面与管理端不受影响）；博采 origin 到齐后在 `frontend/.env` 补上并重建一次：

```bash
cd /opt/agenthub/frontend
# frontend/.env 追加一行（逗号分隔：博采生产 origin + 联调 origin，逐字）
#   VITE_EMBED_ALLOWED_PARENT_ORIGINS=https://<博采平台域名>,<联调 origin>
sudo -u agenthub npm ci
sudo -u agenthub npm run build
# 产物 /opt/agenthub/frontend/dist
```

> 联调结束后移除联调 origin 需**重新构建一次**（第 5.5 节）。

## 2. Nginx 三段式配置（仓库即事实源）

`deploy/nginx/agenthub.conf` 已内含三段式布局，**无需手工拼接**：

| 块 | 监听 | server_name | 承载 |
|---|---|---|---|
| 公网嵌入块 | 80 | `agent.zjmi56.com` | 仅 `/embed/`、`/assets/`、`/api/v1/embed/`、`/api/v1/chat/`、`/api/v1/audio/`，其余 404 |
| 内网客户块 | 80（default） | `agenthub.intra`、`10.128.140.208`、`_` | 客户聊天/登录/联调/健康检查；`/admin` 与 `/api/v1/admin/` 404 |
| 内网管理块 | 81 | `agenthub.intra`、`10.128.140.208`、`_` | 完整站点含管理后台，仅内网 |

安装（基线部署第 8 节已含此步；本表为口径说明）：

```bash
sudo install -m 644 /opt/agenthub/deploy/nginx/agenthub.conf \
                    /etc/nginx/sites-available/agenthub.conf
sudo ln -sfn /etc/nginx/sites-available/agenthub.conf /etc/nginx/sites-enabled/agenthub.conf
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
```

## 3. 后端 .env 调整（208 的 backend/.env）

```text
EMBED_ENABLED=true
EMBED_COOKIE_SECURE=true          # 公网唯一档（ADR-022）：浏览器侧全程 HTTPS，不受影响
EMBED_COOKIE_SAMESITE=none
EMBED_EXTERNAL_TOKEN_SECRET=<我方生成，secrets.token_urlsafe(48)，安全渠道发博采后端>
EMBED_EXTERNAL_TOKEN_ISSUER=industrial-internet
EMBED_EXTERNAL_TOKEN_AUDIENCE=agenthub
EMBED_ALLOWED_PARENT_ORIGINS=https://<博采平台域名>,<联调 origin>
CORS_ALLOWED_ORIGINS=https://agent.zjmi56.com
# AUTH_COOKIE_SECURE 保持 false（内网 80/81 管理通道用 HTTP，公网不承载管理登录）
```

```bash
sudo systemctl restart agenthub-backend
```

## 4. 监听留证

```bash
sudo ss -tlnp | grep nginx
# 期望：只见 80 与 81；208 永不开 443；8240 仅 127.0.0.1
```

公网唯一通路是网关 443→208:80；81 与 8240 公网均不可达。

## 5. 联调测试（博采开发接入）

### 5.1 联调白名单

首选**网关边缘 ACL**（前置条件 12）：只放 `39.183.172.64`（博采开发）+ 我方公司出口 IP。
网关做不了时的兜底：联调期靠「路径收缩 + 粗粒度限流 + embed token 校验」单防线，
**上线前必须重新评估**（第 8 节）。

### 5.2 嵌入方 origin 配置（两处都已含联调 origin）

第 1 步（前端构建）与第 3 步（后端 .env）的 ORIGINS 均为逗号分隔列表，联调 origin
一并写入。漏配表现：iframe 白屏，浏览器控制台报 origin 校验失败；后端 CSP
`frame-ancestors` 不含该 origin 时浏览器直接拒嵌。

### 5.3 三阶段联调

| 阶段 | 内容 | 通过标准 |
|---|---|---|
| 一、纯 API 契约 | 博采开发在其机器 curl `POST /api/v1/embed/exchange`（PyJWT 自签测试 token）；错误 case（过期/错签名/错 iss） | 正常 token 换到 embed session；错误 case 返回预期 401/400 |
| 二、iframe 嵌入 | 博采联调页面嵌 `https://agent.zjmi56.com/embed/chat`，完整走 exchange → 发消息收 SSE | 聊天正常，节点过程可见；**含 ≥2 分钟慢速流专项（专杀网关空闲超时/缓冲）** |
| 三、全真演练 | 博采真实/预发平台嵌入；登出传播切断 | `docs/20260814部署联调要点.md` 阶段三验收清单 |

阶段一 curl 示例（博采开发机 39.183.172.64 执行）：

```bash
curl -X POST https://agent.zjmi56.com/api/v1/embed/exchange \
  -H 'Content-Type: application/json' \
  -d '{"token": "<PyJWT 自签的短期 JWT>"}'
```

### 5.4 联调常见故障

| 现象 | 原因 | 处理 |
|---|---|---|
| iframe 白屏 | 父页面 origin 不在两处 ORIGINS 配置（逐字校验，端口/尾斜杠都算） | 核对第 1/3 步，改前端须重新构建 |
| exchange 401 | JWT 签名/iss/aud/过期时间不符 | 按对接文档 §7 对齐 |
| 聊天返回 mock 应答 | Agent 的 Dify Key 未配/失效 | 管理端（:81）核对 Agent 配置快照 |
| SSE 一次性返回而非逐字 | 网关缓冲了 chunked 响应 | 找网络组关停对该域名的响应缓冲 |
| SSE 中途断流（约 30/60 秒） | 网关空闲超时过短 | 找网络组调到 ≥600s |
| 上传语音 413 | 网关请求体上限 <20MB | 找网络组调大 |
| 偶发 429 | 粗粒度限流阈值偏紧 | 视联调人数调 `agenthub_public` zone |

### 5.5 联调完成后

1. 两处 ORIGINS 移除联调 origin（保留博采生产 origin），**前端需重新构建一次**
2. 白名单去留决策（第 8 节）
3. 按第 6 节验证清单全量过一遍

## 6. 验证清单（逐条过，全绿才算上线）

公网视角（任意能出网的机器，DNS 直指网关，无需 --resolve）：

```bash
# 嵌入页可达
curl -I https://agent.zjmi56.com/embed/chat                       # 200
# embed API 通（未带会话 401 属正常，证明路由通）
curl https://agent.zjmi56.com/api/v1/embed/session                # 401
# ★ 头号项：管理面必须全部被挡（404）——Host 分流 + 端口隔离双保险实测
curl https://agent.zjmi56.com/admin                               # 404
curl https://agent.zjmi56.com/api/v1/admin/agents                 # 404
curl https://agent.zjmi56.com/api/v1/auth/login                   # 404
curl https://agent.zjmi56.com/health                              # 404（健康检查不公网暴露）
# 证书链完整（在网关上，经公网验证）
openssl s_client -connect agent.zjmi56.com:443 -servername agent.zjmi56.com </dev/null 2>/dev/null | openssl x509 -noout -subject -issuer
```

内网视角（确认 80/81 通道分工正确、互不影响）：

```bash
curl -I http://10.128.140.208/          # 200，客户面照旧
curl http://10.128.140.208/health       # {"status":"ok"}
curl -I http://10.128.140.208/admin     # 404（80 已无管理面）
curl http://10.128.140.208/api/v1/admin/agents   # 404
curl -I http://10.128.140.208:81/admin  # 200（管理后台新地址）
curl http://10.128.140.208:81/health    # {"status":"ok"}
```

全真验收：博采测试页嵌入 → 一次性 token exchange → 发一条消息收 SSE 流 →
博采侧登出后智能体停止工作（按 `docs/20260814部署联调要点.md` 阶段三）。

## 7. 回滚（任何时候可整体退回）

```bash
# 公网通路：找网络组撤掉 443→208:80 映射（一刀切，最彻底）
# Nginx：如无公网映射，公网块天然惰性（无 Host 命中的流量），无需改动
# 后端：.env 恢复原值（EMBED_ENABLED=false / origins 还原）
sudo systemctl restart agenthub-backend
```

## 8. 白名单口径（联调 → 上线）

- **联调期**：网关边缘 ACL 只放 `39.183.172.64` + 我方出口（前置条件 12）。
- **上线决策**：博采**生产用户**出口网段可枚举 → 网关 ACL 替换为生产网段继续启用；
  公网任意来源不可枚举 → 撤 ACL，嵌入面靠「路径收缩 + 粗粒度限流 + embed token 校验」
  兜底（ADR-022 口径）。注意 208 本地因 XFF 多层不可还原，**无法**在本地 Nginx 做
  来源白名单，该能力只在网关层存在。
- 操作均为网关侧策略调整 + 我方 `sudo nginx -t && sudo systemctl reload nginx`，零代码改动。

## 9. 收尾（上线验证后）

- 本文件与 `deploy/nginx/agenthub.conf` 即服务器事实源；若服务器配置有现场漂移，
  回传仓库提交，保持一致。
- `DECISIONS.md` ADR-022 修正记录、`CHANGELOG.md` 摘要由架构师维护。

# AgentHub 部署 Runbook（内网三机阵）

本目录是 AgentHub 上生产环境的"骨与血"——配置模板、systemd unit、Nginx、日志轮转、MySQL 备份脚本。
本 README 是**部署主入口**：按章节顺序操作即可把 AgentHub 从代码送上服务器，直到内网用户能登录、问答、看见调用记录。

> ⚠️ **严肃提醒**：所有真实密钥（MySQL 口令、Dify API Key、火山引擎 Key、AUTH_TOKEN_SECRET 等）
> **只能在服务器上手敲填进 `.env`**，绝不允许出现在 git 仓库、聊天记录、运维群里。Agent.md 第 5/7 节是铁律。

---

## 0. 拓扑速览

```
公司内网（10.128.x.x）
┌──────────────────────────────┐    ┌──────────────────────────────┐
│  AgentHub 应用机              │    │  MySQL 数据机                 │
│  10.128.140.208               │    │  10.128.140.211:3306          │
│  agenthub.intra               │◄───┤  mysql.intra                  │
│                              │    │  库: agenthub                 │
│  - Nginx :80  (公开)          │    │  账号: agenthub               │
│  - uvicorn :8240 (仅本机)     │    │  备份账号: agenthub_backup     │
│  - systemd: agenthub-backend  │    └──────────────────────────────┘
└──────────┬───────────────────┘
           │
           ▼
┌──────────────────────────────┐
│  Dify runtime（已就绪）       │
│  10.128.140.209:8200          │
│  dify.intra                   │
└──────────────────────────────┘
```

| 机器 | 内网 IP | 别名 | 端口 | 状态 |
|---|---|---|---|---|
| AgentHub 应用机 | `10.128.140.208` | `agenthub.intra` | 80 (Nginx) / 8240 (本机 uvicorn) | 本次部署目标 |
| MySQL | `10.128.140.211` | `mysql.intra` | 3306 | ✅ 已就绪 |
| Dify | `10.128.140.209` | `dify.intra` | 8200 | ✅ 已就绪 |

---

## 1. 目录与文件清单

```
deploy/
├── README.md                          ★ 本文件，部署主入口
├── hosts.example                      内网 hosts 别名配置样例
├── nginx/
│   └── agenthub.conf                  Nginx 站点配置（HTTP 段启用 / HTTPS 段冷藏）
├── systemd/
│   └── agenthub-backend.service       后端 systemd unit
├── logrotate/
│   └── agenthub                       Nginx 日志轮转规则
└── backup/
    ├── mysql_backup.sh                MySQL 每日全量备份脚本
    └── mysql_backup.cron              备份 cron 调度
```

约定的部署路径：

```
/opt/agenthub/
├── backend/                  ← git checkout 后端代码 + .env
│   ├── .env                  ← 真实密钥（600，agenthub:agenthub）
│   └── ...
├── frontend/
│   └── dist/                 ← npm run build 产物
└── deploy/                   ← 本目录在服务器上的位置
    └── backup/.my.cnf        ← MySQL 备份口令（600）
/var/backups/agenthub/        ← MySQL 备份文件落地
/var/log/agenthub/            ← 应用辅助日志
/var/log/nginx/               ← Nginx 日志
```

---

## 2. 部署前置检查（在你的开发机上完成）

- [ ] **代码可构建**：`cd backend && uv sync && uv run pytest` 全绿
- [ ] **前端可打包**：`cd frontend && npm install && npm run build` 无错误
- [ ] **Dify App 与 Agent API Key 已准备**：管理员登录 Dify 控制台能看到 App，并能复制 API Key
- [ ] **MySQL 账号已就位**：DBA 已建好 `agenthub` 库、`agenthub` 账号、最小权限授权
- [ ] **本机能 SSH 到 10.128.140.208**：`ssh agenthub@10.128.140.208` 通畅

---

## 3. 服务器初始化（agenthub 应用机：10.128.140.208）

> 下面所有命令默认在 `agenthub` 应用机以 `sudo` 用户身份执行。

### 3.1 系统准备

```bash
# 设时区为东八区，否则 cron 调度、日志时间都不直观
sudo timedatectl set-timezone Asia/Shanghai

# 基础工具
sudo apt update
sudo apt install -y nginx git curl ca-certificates logrotate cron \
                    build-essential python3.11 python3.11-venv

# uv（Python 包管理器）
curl -LsSf https://astral.sh/uv/install.sh | sh
sudo mv ~/.local/bin/uv /usr/local/bin/uv
sudo chmod 755 /usr/local/bin/uv
uv --version

# Node.js 20（前端构建用；如前端在开发机上构建好上传 dist，则不必装）
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
```

### 3.2 系统用户与目录

```bash
# 业务用户（无登录 shell、无家目录，仅用于跑后端进程）
sudo useradd --system --no-create-home --shell /usr/sbin/nologin agenthub

# 应用目录
sudo mkdir -p /opt/agenthub
sudo chown agenthub:agenthub /opt/agenthub

# 日志、备份目录
sudo mkdir -p /var/log/agenthub /var/backups/agenthub
sudo chown agenthub:agenthub /var/log/agenthub /var/backups/agenthub
sudo chmod 750 /var/log/agenthub
sudo chmod 700 /var/backups/agenthub
```

### 3.3 hosts 别名

将 `deploy/hosts.example` 中的 3 行追加到 `/etc/hosts`：

```bash
sudo tee -a /etc/hosts >/dev/null <<'EOF'

# AgentHub 内网别名
10.128.140.208  agenthub.intra
10.128.140.211  mysql.intra
10.128.140.209  dify.intra
EOF

# 验证
ping -c 1 mysql.intra
ping -c 1 dify.intra
```

---

## 4. 拉取代码

```bash
# 用普通用户拉，再 chown 给 agenthub（避免 .git 里出现 root 文件）
sudo -u agenthub git clone <你的内网 git 仓库地址> /opt/agenthub/repo

# 简洁起见我们把后端、前端、deploy 链到约定路径
sudo ln -sfn /opt/agenthub/repo/backend  /opt/agenthub/backend
sudo ln -sfn /opt/agenthub/repo/frontend /opt/agenthub/frontend
sudo ln -sfn /opt/agenthub/repo/deploy   /opt/agenthub/deploy
```

> 后续更新代码：`cd /opt/agenthub/repo && sudo -u agenthub git pull && sudo systemctl restart agenthub-backend`

---

## 5. 后端环境与依赖

```bash
cd /opt/agenthub/backend
sudo -u agenthub uv sync
```

### 5.1 配置 .env（这一步是密钥落地的唯一时机）

```bash
sudo -u agenthub cp .env.example .env
sudo -u agenthub vim .env
```

`.env` 中要做的事：

| 改动 | 怎么做 |
|---|---|
| `ENVIRONMENT=local` → `ENVIRONMENT=production` | 触发后端密钥强校验 |
| `DEBUG=true` → `DEBUG=false` | 关掉调试模式 |
| `DATABASE_URL` 占位符 | 改为 `mysql+pymysql://agenthub:<密码>@mysql.intra:3306/agenthub?charset=utf8mb4` |
| `TEST_DATABASE_URL` | 生产同上指向 `agenthub_test`；或注释/留空（生产不跑 pytest） |
| `API_KEY_SIGNING_SECRET` | `python3 -c "import secrets; print(secrets.token_urlsafe(48))"` 生成的强随机 |
| `AUTH_TOKEN_SECRET` | 同上，**独立生成一份**，不要复用 |
| `EMBED_ENABLED` | 暂未对接产业互联网时改为 `false`；真实联调时再改 `true` |
| `EMBED_EXTERNAL_TOKEN_SECRET` | 暂随机一份；产业互联网联调时与对方对齐 |
| `DIFY_BASE_URL` | `http://dify.intra:8200/v1` |
| `VOLC_AUDIO_API_KEY` / `VOLC_TTS_SPEAKER` | 启用语音时填，否则留空 |

填完务必：

```bash
sudo chmod 600 /opt/agenthub/backend/.env
sudo chown agenthub:agenthub /opt/agenthub/backend/.env
ls -l /opt/agenthub/backend/.env   # 应为 -rw------- agenthub agenthub
```

### 5.2 数据库迁移

```bash
cd /opt/agenthub/backend
sudo -u agenthub uv run alembic upgrade head
```

> ⚠️ 迁移**绝不**放在 systemd unit 的 ExecStart 里，否则启动失败会被服务重启掩盖。

迁移完后做一次 sanity check：

```bash
# 用 mysql 客户端登录 mysql.intra，检查表数量与字符集
mysql -h mysql.intra -u agenthub -p agenthub -e "
  SELECT COUNT(*) AS tables FROM information_schema.tables WHERE table_schema='agenthub';
  SELECT DEFAULT_CHARACTER_SET_NAME FROM information_schema.SCHEMATA WHERE SCHEMA_NAME='agenthub';
"
# 期望：tables ≥ 16；charset 为 utf8mb4
```

---

## 6. 前端构建与发布

两种选择二选一：

**A. 服务器本地构建（最简单，但要装 Node）：**

```bash
cd /opt/agenthub/frontend
sudo -u agenthub npm ci
sudo -u agenthub npm run build
# 构建产物在 /opt/agenthub/frontend/dist/
```

**B. 开发机构建后上传（服务器无需 Node）：**

```bash
# 开发机
cd frontend && npm ci && npm run build
scp -r dist/ agenthub-deployer@10.128.140.208:/tmp/agenthub-dist/
# 服务器
sudo rsync -a --delete /tmp/agenthub-dist/ /opt/agenthub/frontend/dist/
sudo chown -R agenthub:agenthub /opt/agenthub/frontend/dist
```

Nginx 配置里指向的就是 `/opt/agenthub/frontend/dist`。

---

## 7. 安装 systemd unit

```bash
sudo install -m 644 /opt/agenthub/deploy/systemd/agenthub-backend.service \
                    /etc/systemd/system/agenthub-backend.service
sudo systemctl daemon-reload
sudo systemctl enable --now agenthub-backend

# 查状态
sudo systemctl status agenthub-backend
# 实时日志
sudo journalctl -u agenthub-backend -f
# 健康检查（直连 127.0.0.1）
curl -s http://127.0.0.1:8240/health
# 期望：{"status":"ok"}
```

启动失败排查思路：
- `journalctl -u agenthub-backend -n 200 --no-pager`
- 多半是 `.env` 缺字段 / 密钥太短 / MySQL 连不上 / `uv` 路径不对

---

## 8. 安装 Nginx 站点

```bash
sudo install -m 644 /opt/agenthub/deploy/nginx/agenthub.conf \
                    /etc/nginx/sites-available/agenthub.conf
sudo ln -sfn /etc/nginx/sites-available/agenthub.conf /etc/nginx/sites-enabled/agenthub.conf
# 默认站点可关掉，避免 Host 通配冲突
sudo rm -f /etc/nginx/sites-enabled/default

sudo nginx -t
sudo systemctl reload nginx
```

内网另一台机器测试：

```bash
curl -I http://agenthub.intra/
curl -s http://agenthub.intra/health
curl -s http://10.128.140.208/health   # 别名未生效时的兜底
```

### 8.1 双栈 HTTPS 启用（iframe 嵌入必需，ADR-021）

默认只开 HTTP `:80`。对接产业互联网 iframe 嵌入时按下述步骤启用 443，形成双栈入口；
HTTP 通道保留（后台管理 / API Key server-to-server / 健康检查 / 纯 API 联调），
**不做 80->443 跳转**。

> **前提认知：iframe 嵌入仅 443 通道可用。** embed session Cookie 必须
> `Secure + SameSite=None`，而浏览器对 HTTP 响应中的 `Secure` Cookie 一律拒收，
> 此为浏览器强制行为，无配置可绕。

1. **内网 DNS 与证书**：
   - 向内网 DNS 申请域名指向本机（如 `agenthub.intra.<公司域>`），对接方机器必须能解析，hosts 别名不够；
   - 用公司 CA 签发服务端证书，SAN 带域名，建议同时带 IP SAN 兜底直连；
   - 确认对接方测试浏览器信任公司根 CA（域内一般默认信任，先确认）；
   - 证书/私钥落 `/etc/nginx/`，权限 `600 root:root`。
2. **Nginx HTTPS 段启用**：`nginx/agenthub.conf` 尾部注释好的 HTTPS 段取消注释，
   `server_name` 换内网域名、填证书路径；路由与 HTTP 段一致照抄。
   HTTP 段 `X-Frame-Options: DENY` 保留不动（后端按 `EMBED_ALLOWED_PARENT_ORIGINS`
   输出 CSP `frame-ancestors`，现代浏览器 CSP 优先，是设计如此）。
   改完 `sudo nginx -t && sudo systemctl reload nginx`。
3. **后端 Cookie 两档**（互斥，切换必须 `sudo systemctl restart agenthub-backend`，
   两档签发的 session 互不通用）：

   | 档 | 配置 | 用途 |
   |---|---|---|
   | HTTP 联调档 | `EMBED_COOKIE_SECURE=false` + `EMBED_COOKIE_SAMESITE=lax` | 同站 HTTP 联调阶段 |
   | HTTPS 正式档 | `EMBED_COOKIE_SECURE=true` + `EMBED_COOKIE_SAMESITE=none` | 跨站 iframe 与生产 |

   双栈下 `AUTH_COOKIE_SECURE` 保持 `false`（后台管理走 HTTP 也要能种 Cookie；
   可信内网妥协，ADR-021 记录在案）。
4. **防火墙口径**：80 与 443 放行，源地址用对接方出口网段白名单（不要写 `/0`）；
   8240（uvicorn loopback）永不对外。变更前后 `sudo ss -tlnp | grep nginx` 留证。

联调三阶段（纯 API 契约 -> 浏览器全链路 HTTP -> 跨站全真 HTTPS）与坑速查见
`docs/20260814部署联调要点.md`。

---

## 9. 日志轮转

```bash
sudo install -m 644 /opt/agenthub/deploy/logrotate/agenthub \
                    /etc/logrotate.d/agenthub
# 语法检查（debug 模式，不实际改）
sudo logrotate -d /etc/logrotate.d/agenthub
```

后端日志已由 journald 接管（systemd unit 配置了 `StandardOutput=journal`），
journald 自身的保留策略在 `/etc/systemd/journald.conf`：

```bash
# 推荐配置
sudo sed -i 's/^#*SystemMaxUse=.*/SystemMaxUse=2G/' /etc/systemd/journald.conf
sudo sed -i 's/^#*MaxRetentionSec=.*/MaxRetentionSec=30day/' /etc/systemd/journald.conf
sudo systemctl restart systemd-journald
```

---

## 10. MySQL 备份（在 AgentHub 应用机执行，远程连 MySQL）

```bash
# 1. 让 DBA 在 mysql.intra 上创建只读备份账号，授权略（见 mysql_backup.sh 注释）
# 2. 在应用机生成 .my.cnf（只放备份口令）
sudo -u agenthub tee /opt/agenthub/deploy/backup/.my.cnf >/dev/null <<'EOF'
[client]
host=mysql.intra
port=3306
user=agenthub_backup
password=<BACKUP_PASSWORD>
EOF
sudo chmod 600 /opt/agenthub/deploy/backup/.my.cnf
sudo chown agenthub:agenthub /opt/agenthub/deploy/backup/.my.cnf

# 3. 给备份脚本执行权限
sudo chmod 750 /opt/agenthub/deploy/backup/mysql_backup.sh

# 4. 手动跑一次，验证产物
sudo -u agenthub /opt/agenthub/deploy/backup/mysql_backup.sh
ls -lh /var/backups/agenthub/
cat /var/log/agenthub/mysql_backup.log

# 5. 安装 cron
sudo install -m 644 /opt/agenthub/deploy/backup/mysql_backup.cron \
                    /etc/cron.d/agenthub-mysql-backup
sudo systemctl restart cron
```

---

## 11. 部署后人工验收（PLAN.md P1 / P5 验收项）

依次在内网另一台机器（或本机浏览器 + 内网代理）执行：

- [ ] `curl http://agenthub.intra/health` 返回 `{"status":"ok"}`
- [ ] 浏览器打开 `http://agenthub.intra/`，看到登录页
- [ ] 用 seed 初始化的演示账号登录成功（如未跑 seed：`uv run python scripts/seed.py`）
- [ ] 进入聊天页，发一条消息，SSE 流式响应正常（Dify 接通）
- [ ] 管理端"调用记录"页能看到刚才那次问答的 `snapshot.retrieval / model / runtime` 三段
- [ ] 浏览器刷新后会话恢复，消息历史完整
- [ ] 各页面时间显示为北京时间（+08:00）
- [ ] `sudo systemctl restart agenthub-backend && curl http://agenthub.intra/health` 仍然 ok
- [ ] 第二天检查 `/var/backups/agenthub/` 有当天的备份文件，且 `gzip -t` 通过

---

## 12. 回滚预案

任何一次发布出问题：

```bash
cd /opt/agenthub/repo
sudo -u agenthub git log --oneline -n 10    # 找到上一个好版本的 commit
sudo -u agenthub git checkout <good_commit>
sudo -u agenthub uv sync
sudo -u agenthub uv run alembic upgrade head   # 注意：迁移不可逆时这一步要慎重
# 前端：把上一个备份 dist 还原回去
sudo systemctl restart agenthub-backend
sudo systemctl reload nginx
```

**强烈建议**：每次发布前对 `/opt/agenthub/frontend/dist` 打一份 tar 压缩备份，发布失败 30 秒就能恢复。

---

## 13. 还没做、留待后续

| 项 | 触发条件 | 对应文档 |
|---|---|---|
| 双栈 HTTPS 启用（内网 CA） | 对接产业互联网 iframe 嵌入时 | 本文件 §8.1 |
| 跨站 iframe Cookie (`Secure=true` / `SameSite=none`) | 产业互联网真实联调时 | PLAN P3 |
| Redis 接入（token 撤销 / 异步任务） | 业务规模上来后 | DECISIONS.md ADR-011 |
| 多副本 / 负载均衡 | 单实例扛不住时 | `nginx/agenthub.conf` upstream 段 |
| WAF / 安全头加固（CSP / HSTS / Referrer-Policy） | 暴露到非可信网络时 | PLAN P6 |

---

## 14. 出问题先看哪儿

| 现象 | 第一步看 |
|---|---|
| `systemctl status` 显示 failed | `journalctl -u agenthub-backend -n 200` |
| 502 Bad Gateway | 后端没起来，看 systemd 日志；或端口被占 `ss -tlnp \| grep 8240` |
| 前端白屏 | 看浏览器 console 与 network；多半是 `index.html` 缓存或 dist 没传上来 |
| Nginx 起不来 | `sudo nginx -t` 看语法；`/var/log/nginx/error.log` |
| 数据库连不上 | 应用机直接 `mysql -h mysql.intra -u agenthub -p agenthub` 验通 |
| Dify 不响应 | 应用机 `curl -v http://dify.intra:8200/v1/` 验通 |

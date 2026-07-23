# 209 合同审查智能体快速部署手册

本文面向当前代码版本，将 AgentHub 的 `internal` profile 单独部署到 209，供公司内部用户试用合同审查工作台。208 上已有的 `external` 营销智能体不调整；MySQL 继续使用 210，但新建独立数据库和账号；已部署的 Dify 只复用服务，不复用 external App/API Key。

下文按现有网段约定使用：

```text
external AgentHub：10.128.140.208
internal AgentHub：10.128.140.209
MySQL 8：          10.128.140.210
```

若实际完整 IP 不同，统一替换文中的三个地址。

## 0. 先确认当前账号约束

当前版本不能把任意字符串直接作为登录账号：

- 登录页和后端 `LoginRequest` 只接受手机号，登录服务会先执行手机号规范化；非手机号用户名不能登录。
- 密码长度必须为 8～20 位，包含大小写字母和数字，不能含空格、`!#$%`，也不能包含连续 3 位键盘序列。
- `seed.py --profile internal` 在空库中只创建一个内部管理员账号，但名称固定为“管理员”，登录标识来自 `SEED_ADMIN_PHONE`。
- 该管理员登录后默认进入 `/admin/agents`；合同审查入口是 `/internal/contract-review`。

因此快速部署必须先准备一个有效手机号和一个符合规则的密码。显示名可在初始化后改成所需名称，但登录仍使用手机号。如果必须使用“用户名 + 指定密码”原样登录，应先单独改造认证模型和密码策略，不能通过直接写入弱化后的数据库凭证绕过后端校验。

相关代码见：

- [`frontend/src/pages/auth/LoginPage.vue`](../frontend/src/pages/auth/LoginPage.vue)
- [`backend/app/modules/auth/schemas.py`](../backend/app/modules/auth/schemas.py)
- [`backend/app/core/security.py`](../backend/app/core/security.py)
- [`backend/scripts/seed.py`](../backend/scripts/seed.py)

## 1. 最终拓扑与端口

| 组件 | 地址 | 说明 |
|---|---|---|
| internal 前端 | `http://10.128.140.209:8081` | 仅公司内网/VPN可访问 |
| AgentHub backend | `127.0.0.1:8241` | 只允许本机 Nginx 访问 |
| Dify | `http://127.0.0.1:8200/v1` | 示例为 Dify 与 AgentHub 同在 209；按实际端口调整 |
| MinIO API | `http://10.128.140.209:9000` | 浏览器预签名上传地址，必须能被内部客户端访问 |
| MySQL | `10.128.140.210:3306` | 新建 `agenthub_internal` 和专用账号 |

本次不安装 Redis、不启动 Redis 容器，也不启动 arq worker。当前合同审查链路使用 MySQL、MinIO、Dify 和显式 `execute` 接口完成；仓库虽然保留 Redis 客户端依赖和配置默认值，但运行代码没有建立 Redis 连接。

## 2. 部署前准备清单

开始前准备以下信息：

1. 要部署的 Git commit 或 tag。
2. 209 可访问 210 的 `3306/tcp`。
3. Dify 合同审查 App 的独立 API Key 和 App ID；不得复用 208 营销智能体的 Key。
4. 可用的 S3 兼容对象存储。推荐在 209 现有 MinIO 上创建独立 service account，以及 `int-agenthub-raw`、`int-agenthub-parsed` 两个 bucket。
5. 允许访问 8081 的公司内网/VPN CIDR。
6. 一个有效手机号和一个符合第 0 节规则的试用密码。

合同审查 Dify workflow 需要接受以下输入字段：

```text
file_parse_task_id
contract_type
context_text
```

## 3. 在 210 创建独立数据库

由 DBA 在 210 执行，`10.128.140.209` 应替换为 MySQL 实际看到的 209 来源地址：

```sql
CREATE DATABASE agenthub_internal
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_0900_ai_ci;

CREATE USER 'agenthub_int'@'10.128.140.209'
  IDENTIFIED BY '<独立强密码>';

GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, INDEX, DROP, REFERENCES
  ON agenthub_internal.*
  TO 'agenthub_int'@'10.128.140.209';

FLUSH PRIVILEGES;
SHOW GRANTS FOR 'agenthub_int'@'10.128.140.209';
```

同时在 210 的主机防火墙或安全组中，只允许 209 访问 `3306/tcp`。数据库密码写入 `DATABASE_URL` 前必须进行 URL 编码。

## 4. 准备 MinIO 资源

合同审查 Web 页面通过预签名 URL 直接上传文件，因此 MinIO/S3 是必需依赖，不能省略。若 209 已有 MinIO，由管理员完成：

1. 创建 `int-agenthub-raw` 和 `int-agenthub-parsed`。
2. 创建专用 service account，例如 `agenthub-internal`，只允许访问上述两个 bucket。
3. 至少授予 bucket location/list，以及对象 get/put/delete 权限。
4. 为两个 bucket 配置精确 CORS：

```xml
<CORSConfiguration>
  <CORSRule>
    <AllowedOrigin>http://10.128.140.209:8081</AllowedOrigin>
    <AllowedMethod>GET</AllowedMethod>
    <AllowedMethod>HEAD</AllowedMethod>
    <AllowedMethod>PUT</AllowedMethod>
    <AllowedHeader>*</AllowedHeader>
    <ExposeHeader>ETag</ExposeHeader>
    <MaxAgeSeconds>3600</MaxAgeSeconds>
  </CORSRule>
</CORSConfiguration>
```

5. `9000/tcp` 只向公司内网/VPN客户端开放；`9001/tcp` 控制台只向管理员网段开放。

如果 209 尚无 MinIO，应先使用公司批准并固定版本的 MinIO 镜像或安装包部署，数据目录建议独立挂载到 `/data/minio`。不要直接让 AgentHub 使用 Dify 自身未授权的存储账号或 bucket。

## 5. 初始化 209

以下命令以 Ubuntu 22.04/24.04 为例：

```bash
sudo apt update
sudo apt install -y nginx curl git ca-certificates default-mysql-client python3

sudo useradd --system --user-group --no-create-home \
  --shell /usr/sbin/nologin agenthub-internal

sudo install -d -o root -g root -m 0755 \
  /opt/agenthub /opt/agenthub/python /opt/agenthub/venvs /etc/agenthub
```

如果用户已存在，跳过 `useradd`。安装 Node.js 22 LTS 和 uv：

```bash
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt install -y nodejs

curl -LsSf https://astral.sh/uv/install.sh | sh
sudo install -m 0755 "$HOME/.local/bin/uv" /usr/local/bin/uv
sudo env UV_PYTHON_INSTALL_DIR=/opt/agenthub/python \
  /usr/local/bin/uv python install 3.11
```

若 Dify 已占用 209 上的 Nginx 或 Docker 端口，先检查，后续只新增 8081/8241，不覆盖 Dify 配置：

```bash
sudo ss -lntp
```

## 6. 拉取固定代码版本

```bash
sudo git clone <repo-url> /opt/agenthub/repo
sudo git -C /opt/agenthub/repo fetch --tags --prune origin
sudo git -C /opt/agenthub/repo checkout --detach <commit-or-tag>
sudo git -C /opt/agenthub/repo status --short
```

最后一条命令必须无输出。不要把 Git Token 写进仓库 URL、脚本或环境文件。

## 7. 安装 internal 依赖并构建前端

本机只部署 internal，因此不执行双 profile 的 `install_profiles.sh`：

```bash
sudo env UV_PYTHON_INSTALL_DIR=/opt/agenthub/python \
  /usr/local/bin/uv venv --clear --python 3.11 \
  /opt/agenthub/venvs/internal

sudo env UV_PYTHON_INSTALL_DIR=/opt/agenthub/python \
  VIRTUAL_ENV=/opt/agenthub/venvs/internal \
  /usr/local/bin/uv sync \
  --project /opt/agenthub/repo/backend \
  --active --frozen --no-dev --no-install-project --extra internal

cd /opt/agenthub/repo/frontend
sudo npm ci
sudo env VITE_CONTRACT_REVIEW_EXECUTE_TIMEOUT_MS=1800000 \
  npm run build:internal

revision="$(sudo git -C /opt/agenthub/repo rev-parse --short=12 HEAD)"
printf '{"profile":"internal","revision":"%s"}\n' "$revision" \
  | sudo tee /opt/agenthub/repo/frontend/dist/internal/version.json >/dev/null

sudo chown -R root:root \
  /opt/agenthub/venvs/internal \
  /opt/agenthub/repo/frontend/dist/internal
sudo chmod -R a+rX \
  /opt/agenthub/python \
  /opt/agenthub/venvs/internal \
  /opt/agenthub/repo/backend \
  /opt/agenthub/repo/frontend/dist/internal
sudo chmod -R go-w \
  /opt/agenthub/venvs/internal \
  /opt/agenthub/repo/frontend/dist/internal
```

验证 PDF/DOCX 依赖：

```bash
/opt/agenthub/venvs/internal/bin/python -c "import docx, fitz; print('internal dependencies ok')"
```

旧 `.doc` 文件需要另装 LibreOffice；本次快速试用建议只接收 PDF 和 DOCX。

## 8. 创建 internal 环境文件

创建 `/etc/agenthub/internal.env`：

```bash
sudoedit /etc/agenthub/internal.env
```

写入以下模板并替换所有尖括号内容。敏感值使用单引号包裹，使该文件既可由 systemd 读取，也可用于迁移命令；不要写入 `REDIS_URL`。

```dotenv
APP_NAME=AgentHub_Internal
APP_VERSION=0.1.0
ENVIRONMENT=production
DEBUG=false
DEPLOYMENT_PROFILE=internal
API_V1_PREFIX=/api/v1
SERVER_HOST=127.0.0.1
SERVER_PORT=8241
FRONTEND_PORT=8081
PUBLIC_ORIGIN=http://10.128.140.209:8081
LOG_LEVEL=INFO

DATABASE_URL='mysql+pymysql://agenthub_int:<URL编码后的数据库密码>@10.128.140.210:3306/agenthub_internal?charset=utf8mb4'

API_KEY_SIGNING_SECRET='<至少32位独立随机值>'
AUTH_TOKEN_SECRET='<至少32位不同随机值>'
AUTH_COOKIE_NAME=agenthub_internal_session
AUTH_COOKIE_SECURE=false
AUTH_COOKIE_SAMESITE=lax
AUTH_COOKIE_DOMAIN=
ACCESS_TOKEN_EXPIRE_MINUTES=20
SESSION_IDLE_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=7

CORS_ALLOWED_ORIGINS=http://10.128.140.209:8081
INTERNAL_ALLOWED_CIDRS=<公司内网或VPN-CIDR>

EMBED_ENABLED=false

DIFY_BASE_URL=http://127.0.0.1:8200/v1
DIFY_API_KEY=
CONTRACT_REVIEW_DIFY_API_KEY='<合同审查Dify-App-API-Key>'
CONTRACT_REVIEW_RUNTIME_APP_ID='<合同审查Dify-App-ID>'

OBJECT_STORAGE_ENDPOINT=http://10.128.140.209:9000
OBJECT_STORAGE_ACCESS_KEY='<internal专用MinIO-access-key>'
OBJECT_STORAGE_SECRET_KEY='<internal专用MinIO-secret-key>'
OBJECT_STORAGE_REGION=us-east-1
OBJECT_STORAGE_BUCKET_RAW=int-agenthub-raw
OBJECT_STORAGE_BUCKET_PARSED=int-agenthub-parsed
OBJECT_STORAGE_PRESIGN_EXPIRES_SECONDS=900
MINIO_CORS_ALLOWED_ORIGINS=http://10.128.140.209:8081

SEED_ADMIN_PHONE='<有效手机号>'
SEED_ADMIN_PASSWORD='<符合第0节规则的密码>'
```

生成两个独立应用密钥时可分别执行：

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

设置文件权限：

```bash
sudo chown root:root /etc/agenthub/internal.env
sudo chmod 0600 /etc/agenthub/internal.env
sudo -u agenthub-internal test ! -r /etc/agenthub/internal.env
sudo stat -c '%U %G %a %n' /etc/agenthub/internal.env
```

## 9. 执行数据库迁移和初始化

必须在第一次 seed 前确认手机号、密码、Dify Key 和 App ID。seed 是幂等的，但重新执行不会修改已存在管理员的密码。

```bash
sudo bash -c '
set -euo pipefail
set -a
. /etc/agenthub/internal.env
set +a
cd /opt/agenthub/repo/backend
/opt/agenthub/venvs/internal/bin/python -m alembic -c alembic.ini upgrade head
/opt/agenthub/venvs/internal/bin/python scripts/seed.py --profile internal
'
```

production 模式不会在输出中显示密码和原始 API Key。若只需要修改用户显示名，可由 DBA 在 210 执行：

```sql
UPDATE user_account
SET name = '<所需显示名>'
WHERE email = 'admin@agenthub.local'
  AND user_type = 'INTERNAL_EMPLOYEE';
```

该操作不改变登录标识，登录仍使用 `SEED_ADMIN_PHONE`。

## 10. 安装 systemd 服务

复用仓库已有 internal unit：

```bash
sudo install -m 0644 \
  /opt/agenthub/repo/deploy/systemd/agenthub-internal.service \
  /etc/systemd/system/agenthub-internal.service

sudo systemctl daemon-reload
sudo systemd-analyze verify /etc/systemd/system/agenthub-internal.service
sudo systemctl enable agenthub-internal.service
```

## 11. 配置 209 的 Nginx

先创建 allowlist；按实际客户端网段替换示例 CIDR：

```bash
sudoedit /etc/agenthub/internal-allowlist.conf
```

```nginx
allow 127.0.0.1;
allow ::1;
allow <公司内网或VPN-CIDR>;
```

创建 `/etc/nginx/sites-available/agenthub-internal.conf`：

```nginx
upstream agenthub_internal_backend {
    server 127.0.0.1:8241;
    keepalive 32;
}

server {
    listen 8081;
    listen [::]:8081;
    server_name _;
    root /opt/agenthub/repo/frontend/dist/internal;

    include /etc/agenthub/internal-allowlist.conf;
    deny all;

    access_log /var/log/nginx/agenthub-internal.access.log;
    error_log /var/log/nginx/agenthub-internal.error.log warn;
    client_max_body_size 100m;

    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;

    location /api/ {
        proxy_pass http://agenthub_internal_backend;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_set_header Host $http_host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $http_host;
        proxy_connect_timeout 5s;
        proxy_send_timeout 1800s;
        proxy_read_timeout 1800s;
        proxy_buffering off;
        proxy_request_buffering off;
        proxy_cache off;
    }

    location = /health {
        proxy_pass http://agenthub_internal_backend;
        proxy_set_header Host $http_host;
        access_log off;
    }

    location ~ ^/(docs|redoc|openapi\.json)$ { return 404; }

    location ^~ /assets/ {
        try_files $uri =404;
        expires 1y;
        add_header Cache-Control "public, immutable";
        access_log off;
    }

    location = /version.json {
        try_files $uri =404;
        expires -1;
        add_header Cache-Control "no-store";
    }

    location / {
        try_files $uri $uri/ /index.html;
        expires -1;
        add_header Cache-Control "no-store, no-cache, must-revalidate";
    }

    location ~ /\. { deny all; }
}
```

启用配置。不要删除或覆盖 209 上已有的 Dify Nginx 配置：

```bash
sudo ln -sfn \
  /etc/nginx/sites-available/agenthub-internal.conf \
  /etc/nginx/sites-enabled/agenthub-internal.conf
sudo nginx -t
```

## 12. 启动与快速验收

```bash
sudo systemctl start agenthub-internal.service
sudo systemctl reload nginx

curl --fail http://127.0.0.1:8241/health
curl --fail http://127.0.0.1:8081/health
curl --fail http://127.0.0.1:8081/version.json
```

检查服务和日志：

```bash
sudo systemctl status agenthub-internal.service --no-pager
sudo journalctl -u agenthub-internal.service -n 200 --no-pager
sudo tail -n 100 /var/log/nginx/agenthub-internal.error.log
```

从 allowlist 内的客户端浏览器执行：

1. 打开 `http://10.128.140.209:8081`。
2. 使用手机号和合规密码登录。
3. 若登录后进入管理端，直接访问 `http://10.128.140.209:8081/internal/contract-review`。
4. 上传一个小型 DOCX 或文本型 PDF。
5. 确认上传、解析、Dify 执行、规则判敏和原文高亮全部完成。
6. 在 210 检查 `file_parse_task`、`contract_review_task`、`agent_invocation_record` 已写入 `agenthub_internal`，208 使用的外部数据库没有新增内部数据。

验收失败时优先检查：

- 浏览器能否访问预签名 URL 中的 MinIO 地址；
- MinIO CORS 是否精确包含 `http://10.128.140.209:8081`；
- Dify App Key 是否属于合同审查 App，workflow 输入名是否一致；
- `DATABASE_URL` 中密码是否已正确 URL 编码；
- Nginx 1800 秒超时和前端构建时的执行超时是否生效。

## 13. 防火墙与安全边界

- 209：只允许公司内网/VPN访问 `8081/tcp`；如浏览器直传本机 MinIO，只允许同一范围访问 `9000/tcp`。
- 209：`8241` 只监听 `127.0.0.1`，不要对网络放行。
- 209：Dify 若只供本机 AgentHub 调用，优先使用 loopback，不新增公网入口。
- 210：只允许 209 访问 `3306/tcp`，`agenthub_int` 只能访问 `agenthub_internal`。
- 当前为无域名 HTTP，只允许可信内网/VPN试用；不得直接处理未经批准的高敏合同生产数据。
- `/etc/agenthub/internal.env` 必须保持 `root:root 0600`，不得提交到 Git。
- 不部署 Redis，不创建 6379 入站规则。

## 14. 更新与回滚

更新前停止 internal 服务，然后切换固定 commit、重建 internal venv/前端、执行向前 migration，再启动：

```bash
sudo systemctl stop agenthub-internal.service
sudo git -C /opt/agenthub/repo fetch --tags --prune origin
sudo git -C /opt/agenthub/repo checkout --detach <new-commit-or-tag>
```

重新执行第 7 节、第 9 节中的 migration，以及：

```bash
sudo systemctl start agenthub-internal.service
curl --fail http://127.0.0.1:8241/health
```

回滚时切回已验证 commit 并重新构建；不要自动执行 Alembic downgrade。

# 209 合同审查与风控助手快速部署手册

本文面向 AgentHub 最新 `internal` profile，同时覆盖合同审查智能体和风控助手智能体。209 已按本文上一版完成部署时，直接执行 **A 部分增量升级**；首次安装才执行 **B 部分完整部署**。208 上已有的 `external` 营销智能体不调整；MySQL 继续使用 210 的独立 internal 数据库和账号；Dify、MinIO 只复用服务，不复用 external App/API Key、service account 或 bucket。

当前经回归确认的应用功能基线为远程分支 `codex/agenthub-internal-updates` 的 commit `0ca9198`。正式部署时优先使用由该 commit 生成的 tag；尚未打 tag 时可以按下文固定到该 commit，禁止直接部署一个持续移动且未确认 commit 的分支头。

下文按现有网段约定使用：

```text
external AgentHub：10.128.140.208
internal AgentHub：10.128.140.209
MySQL 8：          10.128.140.210
```

若实际完整 IP 不同，统一替换文中的三个地址。

## A. 已部署上一版时的快速升级

### A.1 本次升级内容与边界

本次升级在原合同审查工作台基础上增加或完善：

- 合同审查最近工作记录、条件筛选、历史任务恢复和终态任务逻辑删除；
- 风控助手多文件任务、人工复核、来源证据、Excel 审计底稿导出和最近任务逻辑删除；
- PaddleOCR 官方动态结果 bucket 安全白名单，修复 `PaddleOCR result URL host is not allowed`；
- 两条逻辑删除迁移，升级后 Alembic head 应为 `b6d4e89f2c31`；
- internal seed 幂等注册 `contract-review` 和 `risk-assistant` 两个 Agent。

当前 ERP 对账 change 尚未实施。风控助手可以抽取合同/审批表/结算单、运行现有确定性规则、人工复核并导出审计底稿，但不会查询 ERP，也不应把“未出现 ERP 数量或金额核对”判定为部署失败。

风控文档处理会发生以下云端数据外发，必须在业务和安全审批后才能将开关设为 `true`：

1. 扫描 PDF 上传 PaddleOCR；
2. OCR 带锚点文本发送给阿里百炼 Qwen；
3. 当前 `RISK_DOCUMENT_QWEN_INPUT_MODE=ocr_text`，不会向 Qwen 再上传整份原文件或页面图片。

### A.2 升级前备份与记录

先记录旧版本并确认仓库没有本地修改：

```bash
export AGENTHUB_REPO=/opt/agenthub/repo
export OLD_REVISION="$(sudo git -C "$AGENTHUB_REPO" rev-parse HEAD)"
echo "old revision: $OLD_REVISION"
printf '%s\n' "$OLD_REVISION" | sudo tee /root/agenthub-old-revision >/dev/null
sudo chmod 0600 /root/agenthub-old-revision
sudo git -C "$AGENTHUB_REPO" status --short
```

最后一条命令必须无输出。若有输出，先确认文件来源，不要用 `git reset --hard` 覆盖服务器上的未知修改。

备份环境文件、systemd unit 和 Nginx 配置：

```bash
timestamp="$(date +%Y%m%d_%H%M%S)"
sudo install -d -o root -g root -m 0700 "/root/agenthub-upgrade-$timestamp"
sudo cp -a /etc/agenthub/internal.env "/root/agenthub-upgrade-$timestamp/"
sudo cp -a /etc/systemd/system/agenthub-internal.service \
  "/root/agenthub-upgrade-$timestamp/" 2>/dev/null || true
sudo cp -a /etc/nginx/sites-available/agenthub-internal.conf \
  "/root/agenthub-upgrade-$timestamp/" 2>/dev/null || true
```

升级 migration 前必须备份 `agenthub_internal`。若已按仓库备份规范准备 `/etc/agenthub/backup/internal.my.cnf`，执行：

```bash
sudo bash "$AGENTHUB_REPO/deploy/backup/mysql_backup_profile.sh" \
  internal agenthub_internal
sudo ls -lh /var/backups/agenthub/internal/ | tail
```

否则由 DBA 先创建数据库快照或等价的可恢复备份，再继续升级。

### A.3 补齐风控助手环境变量

不要用示例文件整体覆盖已有 `/etc/agenthub/internal.env`，只追加或修改缺少的变量。先执行：

```bash
sudoedit /etc/agenthub/internal.env
```

补齐以下配置。真实 token/key 只写入服务器环境文件，不写入 Git、部署命令、聊天记录或日志：

```dotenv
# 风控助手：PaddleOCR 负责 OCR/位置，Qwen 只负责 OCR 文本语义字段选择。
RISK_DOCUMENT_EXTRACTION_PROVIDER=paddleocr_qwen
RISK_DOCUMENT_CLOUD_EGRESS_ENABLED=true
RISK_DOCUMENT_PADDLEOCR_JOB_URL=https://paddleocr.aistudio-app.com/api/v2/ocr/jobs
RISK_DOCUMENT_PADDLEOCR_API_TOKEN='<PaddleOCR API Token>'
RISK_DOCUMENT_PADDLEOCR_MODEL=PaddleOCR-VL-1.6
# 这里只写主机名模式，不带 https:// 和路径；* 只匹配一个 DNS 标签内部。
RISK_DOCUMENT_PADDLEOCR_RESULT_HOSTS=paddleocr-store-*.bj.bcebos.com

RISK_DOCUMENT_QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
RISK_DOCUMENT_QWEN_API_KEY='<阿里百炼 API Key>'
RISK_DOCUMENT_QWEN_MODEL=qwen3.7-plus
RISK_DOCUMENT_QWEN_INPUT_MODE=ocr_text
```

同时确认原有合同审查和对象存储配置仍存在且有效：

```dotenv
CONTRACT_REVIEW_DIFY_API_KEY='<合同审查 Dify App API Key>'
CONTRACT_REVIEW_RUNTIME_APP_ID='<合同审查 Dify App ID>'
OBJECT_STORAGE_ENDPOINT=http://10.128.140.209:9000
OBJECT_STORAGE_ACCESS_KEY='<internal 专用 MinIO access key>'
OBJECT_STORAGE_SECRET_KEY='<internal 专用 MinIO secret key>'
OBJECT_STORAGE_BUCKET_RAW=int-agenthub-raw
OBJECT_STORAGE_BUCKET_PARSED=int-agenthub-parsed
```

如果云端数据外发尚未审批，必须保持 `RISK_DOCUMENT_CLOUD_EGRESS_ENABLED=false`。此时合同审查仍可使用，但风控任务首次执行会明确失败，不能以填写假 token 的方式绕过。

恢复并核对权限：

```bash
sudo chown root:root /etc/agenthub/internal.env
sudo chmod 0600 /etc/agenthub/internal.env
sudo -u agenthub-internal test ! -r /etc/agenthub/internal.env
sudo stat -c '%U %G %a %n' /etc/agenthub/internal.env
```

209 必须能通过 HTTPS 访问 PaddleOCR、阿里百炼以及 PaddleOCR 返回的 `paddleocr-store-*.bj.bcebos.com` 动态结果域名。若出口防火墙采用 FQDN 白名单，应同步放行这些目标；不要把结果域名固定成某一个带编号的 bucket。

### A.4 拉取固定版本并重建运行环境

当前未打 tag 时，按以下方式获取已经 review 的远程分支并固定到 commit `0ca9198`：

```bash
sudo systemctl stop agenthub-internal.service

sudo git -C "$AGENTHUB_REPO" fetch origin \
  codex/agenthub-internal-updates
sudo git -C "$AGENTHUB_REPO" checkout --detach 0ca9198
sudo git -C "$AGENTHUB_REPO" status --short
sudo git -C "$AGENTHUB_REPO" log -1 --oneline
```

`status --short` 必须无输出，`log` 必须显示目标 commit。若代码已经合并并打 tag，把 `0ca9198` 替换为已批准的 tag/commit。

原地重建 internal venv：

```bash
sudo env UV_PYTHON_INSTALL_DIR=/opt/agenthub/python \
  /usr/local/bin/uv venv --clear --python 3.11 \
  /opt/agenthub/venvs/internal

sudo env UV_PYTHON_INSTALL_DIR=/opt/agenthub/python \
  VIRTUAL_ENV=/opt/agenthub/venvs/internal \
  /usr/local/bin/uv sync \
  --project "$AGENTHUB_REPO/backend" \
  --active --frozen --no-dev --no-install-project --extra internal

/opt/agenthub/venvs/internal/bin/python -c \
  "import docx, fitz, langgraph, openpyxl; print('internal dependencies ok')"
```

重建 internal 前端。两个长任务超时统一设置为 30 分钟：

```bash
cd "$AGENTHUB_REPO/frontend"
sudo npm ci
sudo env \
  VITE_CONTRACT_REVIEW_EXECUTE_TIMEOUT_MS=1800000 \
  VITE_RISK_ASSISTANT_EXECUTE_TIMEOUT_MS=1800000 \
  npm run build:internal

revision="$(sudo git -C "$AGENTHUB_REPO" rev-parse --short=12 HEAD)"
printf '{"profile":"internal","revision":"%s"}\n' "$revision" \
  | sudo tee "$AGENTHUB_REPO/frontend/dist/internal/version.json" >/dev/null

sudo chown -R root:root \
  /opt/agenthub/venvs/internal \
  "$AGENTHUB_REPO/frontend/dist/internal"
sudo chmod -R a+rX \
  /opt/agenthub/python \
  /opt/agenthub/venvs/internal \
  "$AGENTHUB_REPO/backend" \
  "$AGENTHUB_REPO/frontend/dist/internal"
sudo chmod -R go-w \
  /opt/agenthub/venvs/internal \
  "$AGENTHUB_REPO/frontend/dist/internal"
```

### A.5 配置自检、数据库迁移与 seed

已有环境文件来自本文上一版，通常可被 shell 安全加载。若某个值包含空格或 shell 特殊字符，必须先用单引号包裹；随后执行：

```bash
sudo bash -c '
set -euo pipefail
set -a
. /etc/agenthub/internal.env
set +a
cd /opt/agenthub/repo/backend

/opt/agenthub/venvs/internal/bin/python -c "
from app.core.config import get_settings
from app.modules.risk_assessment.extraction.provider_factory import create_document_extraction_provider
s = get_settings()
assert s.deployment_profile.value == \"internal\"
create_document_extraction_provider(s)
print(\"internal config and risk extraction provider ok\")
"

/opt/agenthub/venvs/internal/bin/python -m alembic -c alembic.ini current
/opt/agenthub/venvs/internal/bin/python -m alembic -c alembic.ini upgrade head
/opt/agenthub/venvs/internal/bin/python -m alembic -c alembic.ini current
/opt/agenthub/venvs/internal/bin/python scripts/seed.py --profile internal
'
```

升级后的最后一次 `alembic current` 应显示：

```text
b6d4e89f2c31 (head)
```

seed 是幂等操作：已有管理员和合同审查 Agent 不会重复创建，同时会创建或更新 `risk-assistant` Agent。不要为了注册风控助手直接修改数据库。

### A.6 更新服务单元并启动

```bash
sudo install -m 0644 \
  "$AGENTHUB_REPO/deploy/systemd/agenthub-internal.service" \
  /etc/systemd/system/agenthub-internal.service
sudo systemctl daemon-reload
sudo systemd-analyze verify \
  /etc/systemd/system/agenthub-internal.service

sudo nginx -t
sudo systemctl start agenthub-internal.service
sudo systemctl reload nginx
```

本次不要求覆盖 209 上现有的 Dify Nginx 配置。AgentHub internal server 仍应满足：

- 前端根目录为 `/opt/agenthub/repo/frontend/dist/internal`；
- `/api/` 代理到 `127.0.0.1:8241`；
- `proxy_read_timeout` 和 `proxy_send_timeout` 至少为 `1800s`；
- `8081` 仍受 `/etc/agenthub/internal-allowlist.conf` 和 `deny all` 保护。

### A.7 自动化快速验收

```bash
curl --fail http://127.0.0.1:8241/health
curl --fail http://127.0.0.1:8081/health
curl --fail http://127.0.0.1:8081/version.json

curl -sS -o /dev/null -w 'contract-review HTTP %{http_code}\n' \
  http://127.0.0.1:8241/api/v1/internal/contract-review/tasks
curl -sS -o /dev/null -w 'risk-assistant HTTP %{http_code}\n' \
  http://127.0.0.1:8241/api/v1/internal/risk-assistant/tasks

sudo systemctl status agenthub-internal.service --no-pager
sudo journalctl -u agenthub-internal.service -n 200 --no-pager
```

两个未登录业务接口预期返回 `401`，而不是 `404` 或 `500`。`version.json` 的 revision 应对应目标 commit。

### A.8 浏览器人工验收

从 allowlist 内的客户端打开 `http://10.128.140.209:8081` 并登录。

合同审查验收：

1. 打开 `/internal/contract-review`，上传 PDF 或 DOCX 并完成一次审查；
2. 确认 Dify 抽取、后端规则判敏、原文高亮和结果汇总正常；
3. 刷新页面，确认“最近工作记录”可分页、按状态/合同类型/文件名筛选并恢复历史任务；
4. 确认终态任务可以删除，删除后前端不再显示；底层记录采用逻辑删除。

风控助手验收：

1. 打开 `/internal/risk-assistant`，填写业务编号；
2. 上传采购合同、销售合同、供应链业务合同审批表和结算单，逐个声明正确文档类型；当前页面只接受 PDF/DOCX；
3. 启动任务，确认 PaddleOCR、Qwen、LangGraph 节点执行正常，不再出现 `PaddleOCR result URL host is not allowed`；
4. 若进入 `WAITING_REVIEW`，完成至少一项人工复核并确认任务继续执行；
5. 查看业务总览与来源证据，导出 Excel，并确认 workbook 的用户可见内容是“业务总览”sheet；
6. 刷新页面并恢复最近任务，确认终态任务可以逻辑删除。

最后在 `agenthub_internal` 核对新任务只写入 internal 数据库，并确认 208 的 external 数据库没有新增内部任务。

### A.9 常见故障定位

| 现象 | 优先检查 |
|---|---|
| `PaddleOCR result URL host is not allowed` | 代码是否至少为 `0ca9198`；`RISK_DOCUMENT_PADDLEOCR_RESULT_HOSTS` 是否为 `paddleocr-store-*.bj.bcebos.com`；修改后是否重启 backend |
| `risk document cloud egress is disabled` | 外发审批完成后把 `RISK_DOCUMENT_CLOUD_EGRESS_ENABLED` 设为 `true` 并重启；未审批不得绕过 |
| `PaddleOCR job submission/polling/download failed` | Token、服务器出站 HTTPS、DNS、job URL 和 `*.bj.bcebos.com` 出站规则 |
| `Qwen request failed` | `RISK_DOCUMENT_QWEN_BASE_URL` 应为 OpenAI-compatible base URL，检查百炼 Key、模型权限和出站 HTTPS |
| 数据库提示缺少 `deleted_at` 等字段 | Alembic 未升级到 `b6d4e89f2c31`，先停止服务并补 migration |
| 页面没有风控助手或仍是旧界面 | internal 前端未重建、Nginx root 错误或浏览器缓存；先检查 `version.json` |
| 上传失败或浏览器报 CORS | 预签名 URL 中的 MinIO 地址是否可从客户端访问，MinIO CORS 是否包含精确 origin `http://10.128.140.209:8081` |
| 请求约 10～12 分钟后中断 | 重新构建前端时是否设置两个 Vite timeout；Nginx 读写超时是否达到 1800 秒 |

### A.10 回滚

应用回滚不自动执行 Alembic downgrade。本次新增字段均为 nullable，旧代码通常可以忽略，优先只回滚代码和构建产物：

```bash
sudo systemctl stop agenthub-internal.service
OLD_REVISION="$(sudo cat /root/agenthub-old-revision)"
sudo git -C /opt/agenthub/repo checkout --detach "$OLD_REVISION"
```

然后使用旧 commit 重复 A.4 的 venv/前端构建步骤，重新安装该 commit 的 systemd unit并启动：

```bash
sudo systemctl start agenthub-internal.service
curl --fail http://127.0.0.1:8241/health
```

不要删除新 migration 创建的列，也不要覆盖升级后的业务数据。只有发生无法通过应用回滚解决的数据问题时，才在停服状态下由 DBA 使用 A.2 的备份恢复。保留新增风控环境变量不会影响不读取它们的旧代码。

## B. 首次部署参考

### B.0 先确认当前账号约束

当前版本不能把任意字符串直接作为登录账号：

- 登录页和后端 `LoginRequest` 只接受手机号，登录服务会先执行手机号规范化；非手机号用户名不能登录。
- 密码长度必须为 8～20 位，包含大小写字母和数字，不能含空格、`!#$%`，也不能包含连续 3 位键盘序列。
- `seed.py --profile internal` 在空库中只创建一个内部管理员账号，但名称固定为“管理员”，登录标识来自 `SEED_ADMIN_PHONE`。
- 该管理员登录后默认进入 `/admin/agents`；合同审查入口是 `/internal/contract-review`，风控助手入口是 `/internal/risk-assistant`。

因此快速部署必须先准备一个有效手机号和一个符合规则的密码。显示名可在初始化后改成所需名称，但登录仍使用手机号。如果必须使用“用户名 + 指定密码”原样登录，应先单独改造认证模型和密码策略，不能通过直接写入弱化后的数据库凭证绕过后端校验。

相关代码见：

- [`frontend/src/pages/auth/LoginPage.vue`](../frontend/src/pages/auth/LoginPage.vue)
- [`backend/app/modules/auth/schemas.py`](../backend/app/modules/auth/schemas.py)
- [`backend/app/core/security.py`](../backend/app/core/security.py)
- [`backend/scripts/seed.py`](../backend/scripts/seed.py)

### B.1 最终拓扑与端口

| 组件 | 地址 | 说明 |
|---|---|---|
| internal 前端 | `http://10.128.140.209:8081` | 仅公司内网/VPN可访问 |
| AgentHub backend | `127.0.0.1:8241` | 只允许本机 Nginx 访问 |
| Dify | `http://127.0.0.1:8200/v1` | 示例为 Dify 与 AgentHub 同在 209；按实际端口调整 |
| MinIO API | `http://10.128.140.209:9000` | 浏览器预签名上传地址，必须能被内部客户端访问 |
| MySQL | `10.128.140.210:3306` | 新建 `agenthub_internal` 和专用账号 |
| PaddleOCR | `https://paddleocr.aistudio-app.com` | 风控扫描件 OCR，209 主动出站访问 |
| 阿里百炼 Qwen | `https://dashscope.aliyuncs.com` | 风控 OCR 文本语义字段选择，209 主动出站访问 |

本次不安装 Redis、不启动 Redis 容器，也不启动 arq worker。合同审查使用 MySQL、MinIO、Dify 和显式 `execute` 接口；风控助手使用 MySQL、MinIO、PaddleOCR、Qwen、LangGraph 和显式 `execute/reviews/export` 接口。仓库虽然保留 Redis 客户端依赖和配置默认值，但这两条链路当前没有建立 Redis 连接。

### B.2 部署前准备清单

开始前准备以下信息：

1. 要部署的 Git commit 或 tag。
2. 209 可访问 210 的 `3306/tcp`。
3. Dify 合同审查 App 的独立 API Key 和 App ID；不得复用 208 营销智能体的 Key。
4. 可用的 S3 兼容对象存储。推荐在 209 现有 MinIO 上创建独立 service account，以及 `int-agenthub-raw`、`int-agenthub-parsed` 两个 bucket。
5. 允许访问 8081 的公司内网/VPN CIDR。
6. 一个有效手机号和一个符合第 0 节规则的试用密码。
7. PaddleOCR API Token、阿里百炼 API Key，以及 `qwen3.7-plus` 模型调用权限。
8. 原始合同/扫描件出站 PaddleOCR、OCR 文本出站 Qwen 的业务与安全审批；未审批时风控助手保持关闭。

合同审查 Dify workflow 需要接受以下输入字段：

```text
file_parse_task_id
contract_type
context_text
```

### B.3 在 210 创建独立数据库

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

### B.4 准备 MinIO 资源

合同审查和风控助手 Web 页面都通过预签名 URL 直接上传文件，因此 MinIO/S3 是必需依赖，不能省略。若 209 已有 MinIO，由管理员完成：

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

### B.5 初始化 209

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

### B.6 拉取固定代码版本

```bash
sudo git clone <repo-url> /opt/agenthub/repo
sudo git -C /opt/agenthub/repo fetch --tags --prune origin
sudo git -C /opt/agenthub/repo checkout --detach <commit-or-tag>
sudo git -C /opt/agenthub/repo status --short
```

最后一条命令必须无输出。不要把 Git Token 写进仓库 URL、脚本或环境文件。

### B.7 安装 internal 依赖并构建前端

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
sudo env \
  VITE_CONTRACT_REVIEW_EXECUTE_TIMEOUT_MS=1800000 \
  VITE_RISK_ASSISTANT_EXECUTE_TIMEOUT_MS=1800000 \
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

验证 PDF/DOCX、LangGraph 和 Excel 导出依赖：

```bash
/opt/agenthub/venvs/internal/bin/python -c \
  "import docx, fitz, langgraph, openpyxl; print('internal dependencies ok')"
```

旧 `.doc` 文件需要另装 LibreOffice；本次快速试用建议只接收 PDF 和 DOCX。

### B.8 创建 internal 环境文件

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

# 完成云端数据外发审批后才可设为 true。
RISK_DOCUMENT_EXTRACTION_PROVIDER=paddleocr_qwen
RISK_DOCUMENT_CLOUD_EGRESS_ENABLED=true
RISK_DOCUMENT_PADDLEOCR_JOB_URL=https://paddleocr.aistudio-app.com/api/v2/ocr/jobs
RISK_DOCUMENT_PADDLEOCR_API_TOKEN='<PaddleOCR-API-Token>'
RISK_DOCUMENT_PADDLEOCR_MODEL=PaddleOCR-VL-1.6
RISK_DOCUMENT_PADDLEOCR_RESULT_HOSTS=paddleocr-store-*.bj.bcebos.com
RISK_DOCUMENT_QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
RISK_DOCUMENT_QWEN_API_KEY='<阿里百炼-API-Key>'
RISK_DOCUMENT_QWEN_MODEL=qwen3.7-plus
RISK_DOCUMENT_QWEN_INPUT_MODE=ocr_text

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

### B.9 执行数据库迁移和初始化

必须在第一次 seed 前确认手机号、密码、Dify Key 和 App ID。seed 是幂等的，但重新执行不会修改已存在管理员的密码。

```bash
sudo bash -c '
set -euo pipefail
set -a
. /etc/agenthub/internal.env
set +a
cd /opt/agenthub/repo/backend
/opt/agenthub/venvs/internal/bin/python -c "
from app.core.config import get_settings
from app.modules.risk_assessment.extraction.provider_factory import create_document_extraction_provider
s = get_settings()
assert s.deployment_profile.value == \"internal\"
create_document_extraction_provider(s)
print(\"internal config and risk extraction provider ok\")
"
/opt/agenthub/venvs/internal/bin/python -m alembic -c alembic.ini upgrade head
/opt/agenthub/venvs/internal/bin/python -m alembic -c alembic.ini current
/opt/agenthub/venvs/internal/bin/python scripts/seed.py --profile internal
'
```

`alembic current` 应显示 `b6d4e89f2c31 (head)`。production 模式不会在输出中显示密码和原始 API Key。internal seed 会同时创建或更新合同审查和风控助手 Agent。若只需要修改用户显示名，可由 DBA 在 210 执行：

```sql
UPDATE user_account
SET name = '<所需显示名>'
WHERE email = 'admin@agenthub.local'
  AND user_type = 'INTERNAL_EMPLOYEE';
```

该操作不改变登录标识，登录仍使用 `SEED_ADMIN_PHONE`。

### B.10 安装 systemd 服务

复用仓库已有 internal unit：

```bash
sudo install -m 0644 \
  /opt/agenthub/repo/deploy/systemd/agenthub-internal.service \
  /etc/systemd/system/agenthub-internal.service

sudo systemctl daemon-reload
sudo systemd-analyze verify /etc/systemd/system/agenthub-internal.service
sudo systemctl enable agenthub-internal.service
```

### B.11 配置 209 的 Nginx

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

### B.12 启动与快速验收

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
3. 访问 `/internal/contract-review`，上传一个小型 DOCX 或文本型 PDF，确认上传、解析、Dify 执行、规则判敏、原文高亮和最近工作记录全部完成。
4. 访问 `/internal/risk-assistant`，上传采购合同、销售合同、供应链业务合同审批表和结算单，声明文档类型并执行。
5. 确认 PaddleOCR/Qwen 抽取、LangGraph、人工复核、来源证据、最近任务和 Excel 导出正常。
6. 在 210 检查 `file_parse_task`、`contract_review_task`、`risk_assessment_task`、`agent_invocation_record` 已写入 `agenthub_internal`，208 使用的外部数据库没有新增内部数据。

验收失败时优先检查：

- 浏览器能否访问预签名 URL 中的 MinIO 地址；
- MinIO CORS 是否精确包含 `http://10.128.140.209:8081`；
- Dify App Key 是否属于合同审查 App，workflow 输入名是否一致；
- PaddleOCR/Qwen Token、模型权限、出站 HTTPS 和动态结果域名是否可用；
- `RISK_DOCUMENT_CLOUD_EGRESS_ENABLED` 是否与审批状态一致；
- `DATABASE_URL` 中密码是否已正确 URL 编码；
- Alembic 是否到达 `b6d4e89f2c31`；
- Nginx 1800 秒超时和两个前端执行超时是否生效。

### B.13 防火墙与安全边界

- 209：只允许公司内网/VPN访问 `8081/tcp`；如浏览器直传本机 MinIO，只允许同一范围访问 `9000/tcp`。
- 209：`8241` 只监听 `127.0.0.1`，不要对网络放行。
- 209：Dify 若只供本机 AgentHub 调用，优先使用 loopback，不新增公网入口。
- 209：按最小范围允许出站访问 PaddleOCR、阿里百炼和 PaddleOCR 动态结果域名；不开放对应入站端口。
- 210：只允许 209 访问 `3306/tcp`，`agenthub_int` 只能访问 `agenthub_internal`。
- 当前为无域名 HTTP，只允许可信内网/VPN试用；不得直接处理未经批准的高敏合同生产数据。
- `/etc/agenthub/internal.env` 必须保持 `root:root 0600`，不得提交到 Git。
- 不部署 Redis，不创建 6379 入站规则。

### B.14 后续更新与回滚

后续版本继续使用 A 部分流程：先备份，停止 internal 服务，切换固定 commit，补齐新增环境变量，重建 internal venv/前端，执行向前 migration 和幂等 seed，再启动并验收。最小命令骨架如下：

```bash
sudo systemctl stop agenthub-internal.service
sudo git -C /opt/agenthub/repo fetch --tags --prune origin
sudo git -C /opt/agenthub/repo checkout --detach <new-commit-or-tag>
```

重新执行第 7 节构建和第 9 节 migration/seed，再启动：

```bash
sudo systemctl start agenthub-internal.service
curl --fail http://127.0.0.1:8241/health
```

回滚时切回已验证 commit 并重新构建；不要自动执行 Alembic downgrade。

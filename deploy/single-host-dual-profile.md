# AgentHub 同机双 profile 试用部署 Runbook

本 Runbook 用于在一台 Ubuntu 应用服务器上，从同一代码 revision 运行 external 营销智能体和 internal 合同审查/风控智能体。MySQL 位于另一台服务器。该形态只适用于受控试用，不替代 `DECISIONS.md` ADR-015 的正式分机目标。

## 0. 上线前安全门槛

- 无域名 HTTP 只允许公司可信内网或 VPN。不得把 8080/8081 直接映射到公网。
- internal 入口必须有明确公司 LAN/VPN CIDR；Nginx 配置始终保留 `deny all`。
- backend 8240/8241 只绑定 `127.0.0.1`，主机防火墙也应显式拒绝外部访问。
- external/internal 不得共享数据库账号/schema、Auth/API Key 签名密钥、Dify App/API Key、MinIO service account/bucket 或 Cookie 名称。
- 真实外部用户或未经脱敏的高敏合同/单据投入使用前，必须启用 HTTPS（内部 CA/IP SAN 或正式域名证书），并完成数据出网、日志留存、备份恢复与访问控制评审。
- 出现公网营销流量、高敏数据生产处理、合规主机隔离要求、资源争抢、独立发布节奏或高可用需求中的任一项时，退出同机模式并迁移 internal 到独立主机。

## 1. 固定拓扑和目录

| 项目 | external | internal |
| --- | --- | --- |
| 浏览器入口 | `http://APP_IP:8080` | `http://APP_IP:8081` |
| backend | `127.0.0.1:8240` | `127.0.0.1:8241` |
| 环境文件 | `/etc/agenthub/external.env` | `/etc/agenthub/internal.env` |
| systemd | `agenthub-external.service` | `agenthub-internal.service` |
| release 指针 | `/opt/agenthub/current-external` | `/opt/agenthub/current-internal` |
| venv 指针 | `/opt/agenthub/venvs/external` | `/opt/agenthub/venvs/internal` |
| 前端 root | `/opt/agenthub/frontend-dist/external/current` | `/opt/agenthub/frontend-dist/internal/current` |

源码 release 位于 `/opt/agenthub/releases/<revision>/`，版本化 venv 位于 `/opt/agenthub/venvs/releases/<profile>/<revision>/`，前端产物位于 `/opt/agenthub/frontend-dist/<profile>/releases/<revision>/`。安装脚本最后原子切换各自 `current` 指针，因此可单独回滚一个 profile。

## 2. 主机前置准备

以 Ubuntu 22.04/24.04 为例安装：

```bash
sudo apt update
sudo apt install -y nginx rsync curl jq git ca-certificates default-mysql-client python3

if ! id -u agenthub >/dev/null 2>&1; then
  sudo useradd --system --user-group --home-dir /opt/agenthub \
    --no-create-home --shell /usr/sbin/nologin agenthub
fi
sudo install -d -o root -g agenthub -m 0755 /opt/agenthub /etc/agenthub
sudo install -d -o root -g agenthub -m 0750 /etc/agenthub/backup
```

安装 Node.js 22 LTS、npm 与 `uv`。Python 3.11 由 uv 管理，避免 Ubuntu 22.04/24.04 系统仓库版本差异：

```bash
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt install -y nodejs

curl -LsSf https://astral.sh/uv/install.sh | sh
sudo install -m 0755 "$HOME/.local/bin/uv" /usr/local/bin/uv
sudo /usr/local/bin/uv python install 3.11

git --version
node --version
npm --version
/usr/local/bin/uv --version
```

安装阶段需要访问远程 Git 仓库、npm registry 和 Python package index；受限内网应先配置公司镜像、代理或离线缓存，不要在执行安装脚本中途临时放开服务器到公网。

主机防火墙示例（CIDR 按实际网络替换）：

```bash
sudo ufw allow from <试用用户或网关CIDR> to any port 8080 proto tcp
sudo ufw allow from <公司LAN或VPN CIDR> to any port 8081 proto tcp
sudo ufw deny 8240/tcp
sudo ufw deny 8241/tcp
```

`ss -lntp` 最终应显示 8240/8241 只监听 `127.0.0.1`，8080/8081 由 Nginx 监听。

### 2.1 从远程仓库拉取固定版本

服务器应使用只读 deploy key 或受控凭证访问远程仓库，不要把访问令牌写进仓库 URL、脚本或命令历史。首次部署：

```bash
git clone <repo-url> "$HOME/agenthub-src"
cd "$HOME/agenthub-src"
git fetch --tags --prune origin
git checkout --detach <commit-sha-or-release-tag>
```

部署前必须确认工作区完全干净，并记录实际 revision。`git status --short` 应无任何输出：

```bash
git status --short
test -z "$(git status --porcelain)"
revision="$(git rev-parse --short=12 HEAD)"
git show -s --format='deploying %H %cI %s' HEAD
```

后续升级不要直接依赖浮动的 `git pull` 结果；先 `git fetch`，再 checkout 已完成测试的 commit SHA 或发布标签，然后重新执行上述干净工作区检查。安装脚本会将该 checkout 复制为 `/opt/agenthub/releases/$revision` 下的不可变 release。

## 3. 远端 MySQL：双 schema、双账号

由 DBA 在 MySQL 服务器创建两个独立 schema 和最小权限账号。以下仅为结构示例，密码必须通过安全通道生成和交付：

```sql
CREATE DATABASE agenthub CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE agenthub_internal CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE USER 'agenthub_ext'@'<APP_SERVER_IP>' IDENTIFIED BY '<strong-random-secret>';
CREATE USER 'agenthub_int'@'<APP_SERVER_IP>' IDENTIFIED BY '<different-strong-random-secret>';
GRANT ALL PRIVILEGES ON agenthub.* TO 'agenthub_ext'@'<APP_SERVER_IP>';
GRANT ALL PRIVILEGES ON agenthub_internal.* TO 'agenthub_int'@'<APP_SERVER_IP>';
```

账号不得相同，也不得给任一运行账号访问另一 schema 的权限。备份账号和恢复演练见 `deploy/backup/dual-profile-backup.md`。

## 4. Dify 与 MinIO 隔离

即使 Dify/MinIO 共用物理宿主，也要准备：

- external 独立 Dify App/API Key；internal 合同审查独立 App/API Key。不要把一个 Key 同时写进两份环境文件。
- external MinIO service account 只能访问 `ext-agenthub-raw`、`ext-agenthub-parsed`。
- internal MinIO service account 只能访问 `int-agenthub-raw`、`int-agenthub-parsed`；内部 bucket 按 ADR-016 启用加密、生命周期和审计。
- internal 预签名上传 CORS 必须精确包含端口，例如 `http://APP_IP:8081`，不得写 `*`。

MinIO CORS XML 示例（对每个 internal bucket 设置）：

```xml
<CORSConfiguration>
  <CORSRule>
    <AllowedOrigin>http://APP_IP:8081</AllowedOrigin>
    <AllowedMethod>PUT</AllowedMethod>
    <AllowedMethod>GET</AllowedMethod>
    <AllowedMethod>HEAD</AllowedMethod>
    <AllowedHeader>*</AllowedHeader>
    <ExposeHeader>ETag</ExposeHeader>
    <MaxAgeSeconds>3000</MaxAgeSeconds>
  </CORSRule>
</CORSConfiguration>
```

浏览器访问预签名 URL 时不应附带 AgentHub Cookie 或 `Authorization`；授权信息仅在预签名 URL 本身。

## 5. 安装两份环境文件

从模板复制后替换所有 `change-me` 和文档 IP：

```bash
cd "$HOME/agenthub-src"
sudo install -m 0640 -o root -g agenthub \
  deploy/profiles/external/.env.example /etc/agenthub/external.env
sudo install -m 0640 -o root -g agenthub \
  deploy/profiles/internal/.env.example /etc/agenthub/internal.env
sudoedit /etc/agenthub/external.env
sudoedit /etc/agenthub/internal.env
```

必须保持：

- `DEPLOYMENT_PROFILE=external|internal` 与文件目标一致。
- `PUBLIC_ORIGIN`、`CORS_ALLOWED_ORIGINS`、`MINIO_CORS_ALLOWED_ORIGINS` 使用实际 IP 和各自端口。
- HTTP 试用：`AUTH_COOKIE_SECURE=false`，Cookie Domain 为空；HTTPS 后改为 `true`。
- external `AUTH_COOKIE_NAME=agenthub_session`；internal `agenthub_internal_session`。
- internal `EMBED_ENABLED=false`；若未来显式启用，必须配置独立 embed Cookie/密钥/parent origins 并重新预检。
- `INTERNAL_ALLOWED_CIDRS` 只填获批的公司 LAN/VPN CIDR，禁止 `0.0.0.0/0` 或 `::/0`。

检查权限：

```bash
sudo stat -c '%U %G %a %n' /etc/agenthub/external.env /etc/agenthub/internal.env
```

## 6. 构建并安装同一 revision

在第 2.1 节已经固定并检查源码 revision 后，从该 checkout 执行：

```bash
cd "$HOME/agenthub-src"
revision="$(git rev-parse --short=12 HEAD)"
sudo bash deploy/scripts/install_profiles.sh "$PWD" "$revision"
```

脚本会：复制不可变 release、创建版本化 external/internal venv、external 仅同步基础依赖、internal 同步 `internal` extra、构建 `dist/external` 与 `dist/internal`、执行产物隔离检查、写入 `version.json`，最后原子切换静态/release/venv 指针。脚本不自动重启服务。

## 7. 安装 systemd 与 Nginx

```bash
sudo install -m 0644 deploy/systemd/agenthub-external.service /etc/systemd/system/
sudo install -m 0644 deploy/systemd/agenthub-internal.service /etc/systemd/system/
sudo systemctl daemon-reload

sudo install -m 0644 deploy/nginx/agenthub-single-host.conf \
  /etc/nginx/sites-available/agenthub-single-host.conf
sudo ln -sfn /etc/nginx/sites-available/agenthub-single-host.conf \
  /etc/nginx/sites-enabled/agenthub-single-host.conf
sudo rm -f /etc/nginx/sites-enabled/default
```

从 internal EnvironmentFile 生成 allowlist（输出只含 CIDR）：

```bash
tmp_allowlist="$(mktemp)"
sudo /opt/agenthub/venvs/internal/bin/python \
  /opt/agenthub/current-internal/deploy/scripts/render_nginx_allowlist.py \
  --env /etc/agenthub/internal.env >"$tmp_allowlist"
sudo install -m 0644 "$tmp_allowlist" /etc/agenthub/internal-allowlist.conf
rm -f "$tmp_allowlist"
```

语法检查必须通过后才能 reload：

```bash
sudo systemd-analyze verify \
  /etc/systemd/system/agenthub-external.service \
  /etc/systemd/system/agenthub-internal.service
sudo nginx -t
```

## 8. 无秘密预检

先运行全量预检；不要使用 `--config-only` 作为上线依据：

```bash
sudo /opt/agenthub/venvs/internal/bin/python \
  /opt/agenthub/current-internal/deploy/scripts/preflight.py \
  --external-env /etc/agenthub/external.env \
  --internal-env /etc/agenthub/internal.env
```

预检覆盖 profile、端口、loopback、Cookie、双库账号/schema、签名/Auth/Dify/MinIO 凭证复用、bucket、CORS、internal allowlist、embed、external 不含 PyMuPDF、internal 解析依赖、双前端产物和版本元数据。报告只输出字段名和问题类别，不输出配置值。

## 9. 两次 migration 与 profile-aware seed

在任何写库动作前，包装脚本都会同时加载两份 EnvironmentFile 并拒绝同一数据库 URL、账号或 schema：

```bash
sudo /opt/agenthub/venvs/internal/bin/python \
  /opt/agenthub/current-internal/deploy/scripts/run_profile_database.py \
  --external-env /etc/agenthub/external.env \
  --internal-env /etc/agenthub/internal.env \
  --profile both --action all
```

`--action all` 先迁移两个数据库，再分别执行 external/internal seed。生产 seed 不打印密码、原始 API Key、Dify Key 或数据库连接串。若只修复一个 profile，可用 `--profile internal --action migrate|seed`，但仍要求另一环境文件存在，以便执行双库冲突保护。

## 10. 启动顺序与 Smoke

```bash
sudo systemctl enable --now agenthub-external.service
curl --fail http://127.0.0.1:8240/health

sudo systemctl enable --now agenthub-internal.service
curl --fail http://127.0.0.1:8241/health

sudo nginx -t && sudo systemctl reload nginx

sudo /opt/agenthub/venvs/internal/bin/python \
  /opt/agenthub/current-internal/deploy/scripts/smoke_dual_profile.py \
  --external-env /etc/agenthub/external.env \
  --internal-env /etc/agenthub/internal.env
```

Smoke 验证两个 health、两套登录品牌、external internal API=404、internal 未登录 API=401、登录 Cookie 名称隔离和两个 `version.json` revision 一致。脚本不打印密码、Cookie 值、Authorization 或 API Key。

随后按人工清单验收：

1. 同一浏览器分别登录两个端口，可同时保持会话；external 登出/重启不影响 internal，反之亦然。
2. external 完成营销问答 SSE、会话恢复、可选语音和 external 调用记录核对。
3. internal 完成合同文件预签名上传、解析、Dify 执行、规则判敏、原文高亮，核对 internal DB/MinIO。
4. internal 完成风控多文件任务、人工复核和 Excel 导出。
5. 从不在 allowlist 的网络访问 8081，应在到达 Vue/FastAPI 前被 Nginx 403；其它机器直连 8240/8241 应连接失败。

## 11. HTTP、IP SAN HTTPS 与 Cookie 切换

纯 HTTP 会暴露手机号、密码、合同正文和响应内容给同网段中间人，只能作为短期可信内网/VPN试用。

无域名时可由公司内部 CA 签发包含应用服务器 IP 的 SAN 证书；客户端必须信任该 CA。Nginx 两个 server 可继续使用不同端口并加 `ssl`，例如 `https://APP_IP:8080` 与 `https://APP_IP:8081`。切换时同步完成：

- `PUBLIC_ORIGIN`、API CORS、MinIO CORS 改成带端口的 `https://` origin。
- 两份 `AUTH_COOKIE_SECURE=true`；启用 embed 时 `EMBED_COOKIE_SECURE=true`。
- `sudo nginx -t`、全量 preflight 和 smoke（通过 `--ca-file /path/to/internal-ca.pem`）重新通过。
- 确认浏览器证书链无警告后，才允许真实外部用户或高敏数据进入试用。

## 12. 日志、备份和故障定位

```bash
journalctl -t agenthub-external -n 200 --no-pager
journalctl -t agenthub-internal -n 200 --no-pager
tail -f /var/log/nginx/agenthub-external.error.log
tail -f /var/log/nginx/agenthub-internal.error.log
```

安装 `deploy/logrotate/agenthub-dual-profile` 到 `/etc/logrotate.d/agenthub-dual-profile`，用 `logrotate -d` 检查。MySQL 分 profile 备份/恢复见 `deploy/backup/dual-profile-backup.md`。备份失败告警、保留期和季度恢复演练必须分别覆盖两个 schema。

## 13. 独立回滚

回滚只切换失败 profile 的三个指针：backend release、venv、frontend static，然后只重启对应 unit。例如 internal：

```bash
previous_revision=<verified-previous-revision>
sudo ln -s "/opt/agenthub/releases/$previous_revision" /opt/agenthub/current-internal.next
sudo mv -Tf /opt/agenthub/current-internal.next /opt/agenthub/current-internal
sudo ln -s "/opt/agenthub/venvs/releases/internal/$previous_revision" /opt/agenthub/venvs/internal.next
sudo mv -Tf /opt/agenthub/venvs/internal.next /opt/agenthub/venvs/internal
sudo ln -s "releases/$previous_revision" /opt/agenthub/frontend-dist/internal/current.next
sudo mv -Tf /opt/agenthub/frontend-dist/internal/current.next /opt/agenthub/frontend-dist/internal/current
sudo systemctl restart agenthub-internal
```

不要自动执行 Alembic downgrade；先确认数据库 migration 是否向前兼容。internal 回滚期间 external 服务和静态目录不应改动。

## 14. 迁移到正式分机

1. 在新 internal 主机准备相同目录、internal venv/静态产物/EnvironmentFile/systemd/Nginx。
2. 保持既有 internal MySQL schema/账号、Dify App/API Key、MinIO service account/bucket，不复制 external 凭证。
3. 在新主机跑 preflight、migration、smoke 和业务人工验收。
4. 切换 internal 入口 IP/内网 DNS和防火墙，观察稳定后停止旧主机的 `agenthub-internal.service` 与 8081 server。
5. external 主机继续运行，不修改业务 endpoint、service、repository、TaskHandler 或 integration 配置结构。

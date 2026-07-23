# AgentHub 同机双 profile 简化部署 Runbook

本 Runbook 沿用原单实例部署方式：服务器只保留一份 Git checkout，在同一代码目录上运行 external 营销智能体和 internal 合同审查/风控智能体。MySQL 位于另一台服务器。

该方案仅用于可信内网/VPN试用。无域名 HTTP 不得直接暴露公网；真实外部用户或高敏合同投入使用前必须启用 HTTPS 或拆分主机。

## 1. 最终目录和端口

```text
/opt/agenthub/repo/                    # 唯一 Git checkout
/opt/agenthub/python/                  # 共享且可读的 uv Python 3.11
/opt/agenthub/venvs/external/          # external 基础依赖
/opt/agenthub/venvs/internal/          # internal extra
/etc/agenthub/external.env
/etc/agenthub/internal.env
```

| 项目 | external | internal |
| --- | --- | --- |
| 浏览器入口 | `http://APP_IP:8080` | `http://APP_IP:8081` |
| backend | `127.0.0.1:8240` | `127.0.0.1:8241` |
| system user | `agenthub-external` | `agenthub-internal` |
| frontend root | `/opt/agenthub/repo/frontend/dist/external` | `/opt/agenthub/repo/frontend/dist/internal` |
| systemd | `agenthub-external.service` | `agenthub-internal.service` |

不再使用版本化 release、`current-*` 软链接或单 profile 独立回滚。升级和回滚以同一个 Git commit 为单位；两个服务仍可单独重启。

## 2. 服务器初始化

以 Ubuntu 22.04/24.04 为例：

```bash
sudo apt update
sudo apt install -y nginx curl git ca-certificates default-mysql-client python3

if ! id -u agenthub-external >/dev/null 2>&1; then
  sudo useradd --system --user-group --no-create-home \
    --shell /usr/sbin/nologin agenthub-external
fi
if ! id -u agenthub-internal >/dev/null 2>&1; then
  sudo useradd --system --user-group --no-create-home \
    --shell /usr/sbin/nologin agenthub-internal
fi

sudo install -d -o root -g root -m 0755 \
  /opt/agenthub /opt/agenthub/venvs /etc/agenthub
sudo install -d -o root -g root -m 0750 /etc/agenthub/backup
```

安装 Node.js 22 LTS 和 uv：

```bash
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt install -y nodejs

curl -LsSf https://astral.sh/uv/install.sh | sh
sudo install -m 0755 "$HOME/.local/bin/uv" /usr/local/bin/uv
sudo env UV_PYTHON_INSTALL_DIR=/opt/agenthub/python \
  /usr/local/bin/uv python install 3.11
```

服务器需要访问 Git、npm 和 Python package index；受限内网请预先配置公司镜像。

## 3. 拉取固定代码版本

```bash
sudo git clone <repo-url> /opt/agenthub/repo
sudo git -C /opt/agenthub/repo fetch --tags --prune origin
sudo git -C /opt/agenthub/repo checkout --detach <commit-or-tag>
sudo git -C /opt/agenthub/repo status --short
```

最后一条命令必须无输出。不要把 Token 写进仓库 URL 或脚本。

## 4. 准备外部资源

必须准备两套逻辑资源，即使它们共用物理 MySQL、Dify 或 MinIO：

- MySQL：两个 schema、两个最小权限账号；任一账号不得访问另一 schema。
- Dify：external 营销 App/API Key 与 internal 合同审查 App/API Key 不复用。
- MinIO：两个 service account；external 只访问 `ext-*` bucket，internal 只访问 `int-*` bucket。
- MinIO CORS：精确允许带端口的前端 origin，不使用 `*`。

MySQL 示例：

```sql
CREATE DATABASE agenthub CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE agenthub_internal CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE USER 'agenthub_ext'@'<APP_IP>' IDENTIFIED BY '<strong-secret>';
CREATE USER 'agenthub_int'@'<APP_IP>' IDENTIFIED BY '<different-secret>';

GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, INDEX, DROP, REFERENCES
  ON agenthub.* TO 'agenthub_ext'@'<APP_IP>';
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, INDEX, DROP, REFERENCES
  ON agenthub_internal.* TO 'agenthub_int'@'<APP_IP>';
```

## 5. 配置两份环境文件

```bash
cd /opt/agenthub/repo
sudo install -m 0600 -o root -g root \
  deploy/profiles/external/.env.example /etc/agenthub/external.env
sudo install -m 0600 -o root -g root \
  deploy/profiles/internal/.env.example /etc/agenthub/internal.env
sudoedit /etc/agenthub/external.env
sudoedit /etc/agenthub/internal.env
```

逐项替换 `change-me` 和文档 IP。重点确认：

- `DEPLOYMENT_PROFILE`、端口和 `PUBLIC_ORIGIN` 正确；
- 数据库账号/schema、签名密钥、Dify Key、MinIO账号/bucket均不同；
- external/internal Cookie 分别为 `agenthub_session`、`agenthub_internal_session`；
- `AUTH_COOKIE_DOMAIN` 为空；HTTP试用使用 `AUTH_COOKIE_SECURE=false`，HTTPS后改为 `true`；
- external 的三个 seed 密码均已替换；internal 管理员 seed 密码已替换；
- internal `EMBED_ENABLED=false`；
- `INTERNAL_ALLOWED_CIDRS` 只包含公司 LAN/VPN CIDR，禁止 `/0`。

环境文件由 systemd 以 root 身份读取，两个运行用户都不应直接读取：

```bash
sudo -u agenthub-external test ! -r /etc/agenthub/internal.env
sudo -u agenthub-external test ! -r /etc/agenthub/external.env
sudo -u agenthub-internal test ! -r /etc/agenthub/external.env
sudo -u agenthub-internal test ! -r /etc/agenthub/internal.env
sudo stat -c '%U %G %a %n' /etc/agenthub/external.env /etc/agenthub/internal.env
```

## 6. 创建 venv 并构建两个前端

首次部署时两个服务尚未启动，可直接执行：

```bash
sudo bash /opt/agenthub/repo/deploy/scripts/install_profiles.sh \
  /opt/agenthub/repo
```

脚本只完成三件事：

1. 重建 `/opt/agenthub/venvs/external` 和 `/opt/agenthub/venvs/internal`；
2. 构建 `frontend/dist/external` 与 `frontend/dist/internal`；
3. 检查依赖和前端产物隔离，并写入 `version.json`。

它不会复制源码、创建 release 目录、切换软链接、迁移数据库或重启服务。

## 7. 安装 systemd 和 Nginx

```bash
cd /opt/agenthub/repo
sudo install -m 0644 deploy/systemd/agenthub-external.service /etc/systemd/system/
sudo install -m 0644 deploy/systemd/agenthub-internal.service /etc/systemd/system/
sudo systemctl daemon-reload

sudo install -m 0644 deploy/nginx/agenthub-single-host.conf \
  /etc/nginx/sites-available/agenthub-single-host.conf
sudo ln -sfn /etc/nginx/sites-available/agenthub-single-host.conf \
  /etc/nginx/sites-enabled/agenthub-single-host.conf
sudo rm -f /etc/nginx/sites-enabled/default
```

生成 internal allowlist：

```bash
tmp_allowlist="$(mktemp)"
sudo /opt/agenthub/venvs/internal/bin/python \
  /opt/agenthub/repo/deploy/scripts/render_nginx_allowlist.py \
  --env /etc/agenthub/internal.env >"$tmp_allowlist"
sudo install -m 0644 "$tmp_allowlist" /etc/agenthub/internal-allowlist.conf
rm -f "$tmp_allowlist"

sudo systemd-analyze verify \
  /etc/systemd/system/agenthub-external.service \
  /etc/systemd/system/agenthub-internal.service
sudo nginx -t
```

## 8. 预检、迁移和初始化

```bash
sudo /opt/agenthub/venvs/internal/bin/python \
  /opt/agenthub/repo/deploy/scripts/preflight.py \
  --external-env /etc/agenthub/external.env \
  --internal-env /etc/agenthub/internal.env

sudo /opt/agenthub/venvs/internal/bin/python \
  /opt/agenthub/repo/deploy/scripts/run_profile_database.py \
  --external-env /etc/agenthub/external.env \
  --internal-env /etc/agenthub/internal.env \
  --profile both --action all
```

预检失败时不要继续。报告只显示字段名和问题类别，不回显秘密。

## 9. 启动和验收

```bash
sudo systemctl enable --now agenthub-external.service
sudo systemctl enable --now agenthub-internal.service
sudo nginx -t && sudo systemctl reload nginx

curl --fail http://127.0.0.1:8240/health
curl --fail http://127.0.0.1:8241/health

sudo /opt/agenthub/venvs/internal/bin/python \
  /opt/agenthub/repo/deploy/scripts/smoke_dual_profile.py \
  --external-env /etc/agenthub/external.env \
  --internal-env /etc/agenthub/internal.env
```

人工验收：

1. 同一浏览器可同时登录两个端口，一侧登出或重启不影响另一侧。
2. external 完成营销问答 SSE、会话恢复和调用记录核对。
3. internal 完成合同上传、解析、Dify执行、规则判敏和原文高亮。
4. internal 完成风控多文件任务、人工复核和 Excel 导出。
5. 非 allowlist 网络访问 8081 返回 403；其它机器无法直连 8240/8241。

## 10. 更新与回滚

固定 venv 会被原地重建，因此更新前先停止两个服务：

```bash
sudo systemctl stop agenthub-external.service agenthub-internal.service
sudo git -C /opt/agenthub/repo fetch --tags --prune origin
sudo git -C /opt/agenthub/repo checkout --detach <new-commit-or-tag>
sudo bash /opt/agenthub/repo/deploy/scripts/install_profiles.sh /opt/agenthub/repo

sudo /opt/agenthub/venvs/internal/bin/python \
  /opt/agenthub/repo/deploy/scripts/preflight.py \
  --external-env /etc/agenthub/external.env \
  --internal-env /etc/agenthub/internal.env
sudo /opt/agenthub/venvs/internal/bin/python \
  /opt/agenthub/repo/deploy/scripts/run_profile_database.py \
  --profile both --action migrate

sudo systemctl start agenthub-external.service agenthub-internal.service
```

回滚使用相同流程，把 Git checkout 切回已验证 commit 后重新构建并启动。不要自动执行 Alembic downgrade；先确认 migration 向前兼容。

## 11. 日志、备份和安全门槛

```bash
journalctl -t agenthub-external -n 200 --no-pager
journalctl -t agenthub-internal -n 200 --no-pager
```

日志轮转见 `deploy/logrotate/agenthub-dual-profile`，双库备份见 `deploy/backup/dual-profile-backup.md`。

主机防火墙应只允许获批来源访问 8080/8081，并拒绝外部访问 8240/8241。真实公网营销流量、高敏合同生产处理、合规主机隔离、资源争抢或独立发布需求出现时，停止使用同机方案并迁移 internal 到独立主机。

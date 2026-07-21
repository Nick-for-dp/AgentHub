# Single-host dual-profile 部署契约

本目录保存试用期“同一服务器、同一 IP、不同端口”运行 external/internal 两个完整 AgentHub 实例所需的模板。正式生产仍以 `DECISIONS.md` ADR-015 的分机和网络隔离为目标。

## 固定约定

| 项目 | external | internal |
| --- | --- | --- |
| 前端监听端口 | `8080` | `8081` |
| backend 监听地址 | `127.0.0.1:8240` | `127.0.0.1:8241` |
| 环境文件 | `/etc/agenthub/external.env` | `/etc/agenthub/internal.env` |
| systemd unit | `agenthub-external.service` | `agenthub-internal.service` |
| release 指针 | `/opt/agenthub/current-external` | `/opt/agenthub/current-internal` |
| Python venv | `/opt/agenthub/venvs/external` | `/opt/agenthub/venvs/internal` |
| 前端当前版本 | `/opt/agenthub/frontend-dist/external/current` | `/opt/agenthub/frontend-dist/internal/current` |
| journald 标识 | `agenthub-external` | `agenthub-internal` |
| Nginx access log | `/var/log/nginx/agenthub-external.access.log` | `/var/log/nginx/agenthub-internal.access.log` |
| Nginx error log | `/var/log/nginx/agenthub-external.error.log` | `/var/log/nginx/agenthub-internal.error.log` |

源码 release 使用 `/opt/agenthub/releases/<revision>/`。前端版本使用 `/opt/agenthub/frontend-dist/<profile>/releases/<revision>/`，发布脚本必须先写临时目录，再以符号链接原子切换 `current`。两个 profile 默认部署同一 revision，但 `current-external`、`current-internal` 和两个静态 `current` 必须能独立切回上一版本。

## 不可合并的边界

- 两个 EnvironmentFile、进程、venv、静态 root、日志标识和 Cookie 名称。
- 两个 MySQL schema 和账号；不能仅以不同表前缀代替。
- 两套 Auth/API Key 签名密钥、Dify App/API Key、MinIO service account。
- `ext-*` 与 `int-*` raw/parsed bucket。
- internal 入口 CIDR allowlist；模板在未配置 allowlist 时必须预检失败，并由 Nginx `deny all` 兜底。

示例端口可以按目标服务器冲突情况整体替换，但 external/internal 之间不得相同，且环境模板、systemd、Nginx、预检和 runbook 必须同步修改。

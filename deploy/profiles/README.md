# 双 profile 固定目录约定

试用服务器沿用原单实例部署思路：一份 Git checkout、两个后端进程、两个前端构建目录。

| 项目 | external | internal |
| --- | --- | --- |
| backend | `127.0.0.1:8240` | `127.0.0.1:8241` |
| frontend | `APP_IP:8080` | `APP_IP:8081` |
| system user | `agenthub-external` | `agenthub-internal` |
| env | `/etc/agenthub/external.env` | `/etc/agenthub/internal.env` |
| venv | `/opt/agenthub/venvs/external` | `/opt/agenthub/venvs/internal` |
| frontend root | `/opt/agenthub/repo/frontend/dist/external` | `/opt/agenthub/repo/frontend/dist/internal` |
| systemd | `agenthub-external.service` | `agenthub-internal.service` |

共享源码固定为 `/opt/agenthub/repo`。不再创建版本化 release、`current-*` 软链接或独立前端发布目录。升级和回滚以同一 Git commit 为单位，两个服务仍可分别启动、停止和重启。

uv 管理的 Python 3.11 固定安装到 `/opt/agenthub/python`，确保两个非登录系统用户都能执行各自 venv 中的解释器。

必须保持以下隔离：

- 两个系统用户和两份由 systemd 读取的 `0600 root:root` 环境文件；
- 两个 Python venv，external 不安装 PyMuPDF，internal 安装 `internal` extra；
- 不同数据库账号/schema、Cookie、Dify Key、MinIO service account/bucket；
- internal Nginx 入口显式 allowlist，并始终保留 `deny all`。

完整操作步骤见 `deploy/single-host-dual-profile.md`。

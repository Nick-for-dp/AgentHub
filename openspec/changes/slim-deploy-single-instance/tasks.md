## 1. deploy 双 profile 产物切除

- [ ] 1.1 删除 `deploy/profiles/`（README.md + external/.env.example + internal/.env.example）
- [ ] 1.2 删除 `deploy/scripts/`（6 个脚本）
- [ ] 1.3 删除 `deploy/verification/`（6 个验证脚本）
- [ ] 1.4 删除 `deploy/systemd/agenthub-external.service`、`deploy/systemd/agenthub-internal.service`
- [ ] 1.5 删除 `deploy/nginx/agenthub-single-host.conf`、`deploy/nginx/internal-allowlist.conf.example`
- [ ] 1.6 删除 `deploy/backup/dual-profile-backup.md`、`deploy/backup/mysql_backup_profile.sh`
- [ ] 1.7 删除 `deploy/logrotate/agenthub-dual-profile`
- [ ] 1.8 删除 `deploy/single-host-dual-profile.md`、`deploy/internal-contract-review-209.md`
- [ ] 1.9 `deploy/README.md`：删除指向 `single-host-dual-profile.md` 的引用句
- [ ] 1.10 `deploy/nginx/agenthub.conf`：HTTPS 段注释按 ADR-021 修正——双栈保留 HTTP `:80`、不做 301 跳转；补注「iframe 嵌入仅 443 通道可用（embed Cookie 须 `Secure+SameSite=None`，HTTP 下浏览器拒收 `Secure` Cookie）」，证书示例从 Let's Encrypt 改为内网 CA 口径
- [ ] 1.11 `deploy/README.md`：新增「双栈 HTTPS 启用」一节，覆盖内网 DNS/CA 证书、Nginx HTTPS 段启用、embed Cookie 两档（联调 `secure=false/lax`、正式 `secure=true/none`，切换须重启后端）、防火墙口径（源 IP 白名单放 80+443，8240 永不对外），内容与 `docs/20260814部署联调要点.md` 一致

## 2. 验证

- [ ] 2.1 保留件核对：`deploy/README.md`、`deploy/nginx/agenthub.conf`、`deploy/systemd/agenthub-backend.service`、`deploy/logrotate/agenthub`、`deploy/backup/mysql_backup.sh`、`deploy/backup/mysql_backup.cron`、`deploy/hosts.example` 齐全，无其他残留文件
- [ ] 2.2 `deploy/README.md` 无双 profile 引用，文档内链接有效，单实例 Runbook 叙述完整
- [ ] 2.3 `CHANGELOG.md` 追加 deploy 切除摘要；归档本 change

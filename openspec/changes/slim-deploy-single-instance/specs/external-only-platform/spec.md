# external-only-platform

## ADDED Requirements

### Requirement: 单实例部署模板

`deploy/` MUST 只保留单实例部署模板，MUST 不包含双 profile 部署脚手架（profiles 目录、双 profile 脚本、双 systemd unit、双 nginx 配置、双 profile 备份与验证产物）。

#### Scenario: deploy 目录只含单实例模板

- WHEN 查看 `deploy/` 目录
- THEN 只存在单实例模板文件（`README.md`、`nginx/agenthub.conf`、`systemd/agenthub-backend.service`、`logrotate/agenthub`、`backup/mysql_backup.sh`、`backup/mysql_backup.cron`、`hosts.example`）
- AND 不存在 `profiles/`、`scripts/`、`verification/` 目录
- AND 不存在双 profile 的 systemd/nginx/backup/logrotate 变体与双 profile 部署文档

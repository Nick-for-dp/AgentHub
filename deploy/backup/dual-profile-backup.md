# 双 profile 备份与恢复约定

external/internal 必须使用两个远端 MySQL schema 和两个账号。备份也按 profile 分离：

- 凭证：`/etc/agenthub/backup/external.my.cnf`、`/etc/agenthub/backup/internal.my.cnf`，权限 `0600`。
- 产物：`/var/backups/agenthub/external/`、`/var/backups/agenthub/internal/`，权限 `0700`。
- 日志：`/var/log/agenthub/external-mysql-backup.log`、`internal-mysql-backup.log`。
- 命令：`mysql_backup_profile.sh external agenthub` 与 `mysql_backup_profile.sh internal agenthub_internal`。

两个 `.my.cnf` 应使用不同的只读备份账号，分别只授予目标 schema 的 `SELECT, LOCK TABLES, SHOW VIEW, PROCESS, EVENT, TRIGGER`。恢复演练应写入各自的隔离恢复库，核对 Alembic revision、关键资源数量和 profile 专属 Agent 后再切换；不得把 external 备份恢复到 internal schema，反之亦然。

应用日志通过 `journalctl -t agenthub-external` 与 `journalctl -t agenthub-internal` 分别定位；Nginx 日志由 `deploy/logrotate/agenthub-dual-profile` 分别轮转。内部审计保留期不得低于 ADR-015 要求。

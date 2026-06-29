#!/usr/bin/env bash
# AgentHub MySQL 备份脚本
#
# 部署位置：/opt/agenthub/deploy/backup/mysql_backup.sh
# 执行用户：agenthub（系统用户）；用 cron 触发，见 mysql_backup.cron
# 权限：chmod 750 mysql_backup.sh
#
# 设计原则（PLAN.md P5 验收项）：
#   - 每日全量备份，保留 14 天滚动
#   - 备份产物文件名带日期戳，便于审计
#   - 备份完成后做最基本的"非空"校验，失败直接非零退出码
#   - 备份失败要被 cron 捕捉（cron 默认会把 stderr 邮件给 root；
#     如未配 MTA，可在 mysql_backup.cron 里改用日志重定向 + 监控系统抓取）
#
# 备份策略（适合 MVP 量级；日后量大再切到 xtrabackup / 主从）：
#   mysqldump --single-transaction 在 InnoDB 表上保持一致性快照，不锁表。
#   --routines --events --triggers 保住存储过程、事件、触发器；当前未必用得到但便宜。
#   --set-gtid-purged=OFF 防止跨实例恢复时 GTID 冲突；本机恢复也无害。
#
# 安全：
#   - 密码用 my.cnf 的 [client] / [mysqldump] 段提供，不出现在命令行（ps 可见）。
#   - 备份文件含全部用户、Cookie 哈希、API Key 哈希等敏感数据，
#     目录权限 700、文件 600，长期备份请加传输加密。

set -euo pipefail

# ─────────────── 配置 ───────────────
# MySQL 连接：使用 /opt/agenthub/deploy/backup/.my.cnf（chmod 600）保管口令
# 文件内容示例：
#   [client]
#   host=mysql.intra
#   port=3306
#   user=agenthub_backup
#   password=<只读+LOCK TABLES 权限的备份账号密码>
#
# DBA 建账号示例：
#   CREATE USER 'agenthub_backup'@'10.128.140.208' IDENTIFIED BY '<强随机>';
#   GRANT SELECT, LOCK TABLES, SHOW VIEW, PROCESS, EVENT, TRIGGER
#     ON agenthub.* TO 'agenthub_backup'@'10.128.140.208';
MYSQL_CNF="/opt/agenthub/deploy/backup/.my.cnf"
DB_NAME="agenthub"

# 备份目录（建议挂载独立磁盘 / 远程存储）
BACKUP_DIR="/var/backups/agenthub"

# 保留天数
KEEP_DAYS=14

# 日志（cron stderr 重定向到这里，便于事后追查）
LOG_FILE="/var/log/agenthub/mysql_backup.log"

# ─────────────── 准备 ───────────────
mkdir -p "$BACKUP_DIR"
mkdir -p "$(dirname "$LOG_FILE")"
chmod 700 "$BACKUP_DIR"

# 切到一个 agenthub 用户必然可读的工作目录，避免脚本被外部以
# `sudo -u agenthub` 触发时继承到 /root 等不可读目录，导致内部
# find / 系统 getcwd 报 "Failed to restore initial working directory"。
cd "$BACKUP_DIR"

timestamp="$(date +%Y%m%d_%H%M%S)"
out_file="$BACKUP_DIR/${DB_NAME}_${timestamp}.sql.gz"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG_FILE"
}

trap 'log "FAILED at line $LINENO with exit $?"; exit 1' ERR

log "===== backup start ====="
log "target: $out_file"

# ─────────────── 备份 ───────────────
# 注意：mysqldump 走 --defaults-extra-file，密码不出现在 ps。
mysqldump \
    --defaults-extra-file="$MYSQL_CNF" \
    --single-transaction \
    --quick \
    --routines \
    --events \
    --triggers \
    --set-gtid-purged=OFF \
    --default-character-set=utf8mb4 \
    "$DB_NAME" \
    | gzip -c > "$out_file"

# 文件权限收紧
chmod 600 "$out_file"

# ─────────────── 校验 ───────────────
# 最低限度：非空 + 能用 gzip -t 通过
size=$(stat -c '%s' "$out_file")
if [ "$size" -lt 1024 ]; then
    log "ABORT: backup file too small ($size bytes), likely failed"
    exit 2
fi
if ! gzip -t "$out_file" 2>>"$LOG_FILE"; then
    log "ABORT: gzip integrity check failed"
    exit 3
fi
log "OK: size=${size} bytes"

# ─────────────── 清理 ───────────────
# 删除 KEEP_DAYS 之前的旧备份
find "$BACKUP_DIR" -maxdepth 1 -type f -name "${DB_NAME}_*.sql.gz" -mtime +${KEEP_DAYS} -print -delete \
    | while read -r removed; do
        log "removed old: $removed"
    done

log "===== backup done ====="

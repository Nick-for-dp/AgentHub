#!/usr/bin/env bash
# Back up one remote AgentHub MySQL schema without exposing credentials in argv.

set -euo pipefail

usage() {
    echo "usage: $0 <external|internal> <database-name>" >&2
    exit 64
}

profile="${1:-}"
database_name="${2:-}"
case "$profile" in
    external|internal) ;;
    *) usage ;;
esac
[[ "$database_name" =~ ^[A-Za-z0-9_]+$ ]] || usage

mysql_cnf="/etc/agenthub/backup/${profile}.my.cnf"
backup_dir="/var/backups/agenthub/${profile}"
log_dir="/var/log/agenthub"
log_file="${log_dir}/${profile}-mysql-backup.log"
keep_days="${KEEP_DAYS:-14}"

umask 077
install -d -m 0700 "$backup_dir"
install -d -m 0750 "$log_dir"
test -r "$mysql_cnf"

timestamp="$(date +%Y%m%d_%H%M%S)"
output="${backup_dir}/${database_name}_${timestamp}.sql.gz"

log() {
    printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >>"$log_file"
}

trap 'status=$?; log "backup failed (status=${status})"; exit "$status"' ERR
log "backup started for profile=${profile}"

mysqldump \
    --defaults-extra-file="$mysql_cnf" \
    --single-transaction \
    --quick \
    --routines \
    --events \
    --triggers \
    --set-gtid-purged=OFF \
    --default-character-set=utf8mb4 \
    "$database_name" | gzip -c >"$output"

chmod 0600 "$output"
test "$(stat -c '%s' "$output")" -ge 1024
gzip -t "$output"
find "$backup_dir" -maxdepth 1 -type f -name "${database_name}_*.sql.gz" \
    -mtime "+${keep_days}" -delete
log "backup completed for profile=${profile}"

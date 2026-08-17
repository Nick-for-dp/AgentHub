## Context

`deploy/` 当前同时承载单实例模板与双 profile 脚手架。双 profile 形态随 ADR-020 作废：后端 `DEPLOYMENT_PROFILE` 由姊妹提案 `slim-backend-external-only` 移除，前端双产物构建由 `slim-frontend-external-only` 移除，deploy 的双 profile 变体随之失去意义。本设计收口部署模板切除。

## Goals / Non-Goals

**Goals:**
- 删除双 profile 全部脚手架，保留单实例 6 件套。
- `deploy/README.md` 不含 dual-profile 引用。

**Non-Goals:**
- 不改动保留件内容（除 README 删一句 dual-profile 引用）。
- 不新增部署文档与脚本；生产部署固化属 `PLAN.md` P5。

## Decisions

### D1. 保留单实例 6 件套，删除双 profile 脚手架

删除 `deploy/profiles/`、`deploy/scripts/`、`deploy/verification/`、`deploy/systemd/agenthub-external.service`、`deploy/systemd/agenthub-internal.service`、`deploy/nginx/agenthub-single-host.conf`、`deploy/nginx/internal-allowlist.conf.example`、`deploy/backup/dual-profile-backup.md`、`deploy/backup/mysql_backup_profile.sh`、`deploy/logrotate/agenthub-dual-profile`、`deploy/single-host-dual-profile.md`、`deploy/internal-contract-review-209.md`。

保留 `deploy/README.md`（删一句 dual-profile 引用）、`deploy/nginx/agenthub.conf`、`deploy/systemd/agenthub-backend.service`、`deploy/logrotate/agenthub`、`deploy/backup/mysql_backup.sh`、`deploy/backup/mysql_backup.cron`、`deploy/hosts.example`。

## Risks / Trade-offs

- [误删保留件] -> 按 6 件套清单逐个核对删除清单；删除后 `deploy/` 目录树 review 一遍。
- [README 删引用时破坏文档结构] -> 只删指向 `single-host-dual-profile.md` 的引用句，改动后通读一遍确认单实例 Runbook 叙述完整。

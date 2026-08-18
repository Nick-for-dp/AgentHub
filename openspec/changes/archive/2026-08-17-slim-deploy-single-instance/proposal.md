## Why

`DECISIONS.md` ADR-020 已决策：AgentHub 收敛为纯对外智能体平台，只保留 external 一种部署形态。

本文档对应 PLAN.md 之外的新增执行事项：ADR-020 代码层落地的 Phase 3（deploy 切除），瘦身阶段划分见 `ag.md` §5。姊妹提案：`slim-backend-external-only`（Phase 1，后端切除）、`slim-frontend-external-only`（Phase 2，前端切除）。三者技术解耦，可独立评审、独立验证、独立回滚。

`deploy/` 目录约 2/3 内容服务双 profile 部署形态：`profiles/` 双环境样例、`scripts/` 双 profile 脚本、`verification/` 验证脚本、双 systemd unit、双 nginx 配置、双 profile 备份方案、两份双 profile 部署文档。AgentHub 只剩单实例单形态，这些脚手架是死内容，增加部署认知负担；生产部署固化属 `PLAN.md` P5，不在本提案范围。

## What Changes

- 删 `profiles/`、`scripts/`、`verification/`、双 profile 的 systemd/nginx/backup/logrotate 变体、`single-host-dual-profile.md`、`internal-contract-review-209.md`。
- 保留单实例 6 件套（`README.md` 删一句 dual-profile 引用、`agenthub.conf`、`agenthub-backend.service`、`logrotate/agenthub`、`mysql_backup.sh/.cron`、`hosts.example`）。

## Capabilities

### New Capabilities

- `external-only-platform`：新增「单实例部署模板」验收需求。该能力的其余需求由姊妹提案提供：`slim-backend-external-only`（单部署形态、固定 Cookie 名、不引入 internal 依赖）、`slim-frontend-external-only`（前端单产物构建），归档时合并为同一能力规格。

### Modified Capabilities

无。

## Impact

- **受影响文件**：`deploy/` 约 2/3 内容删除；保留单实例 6 件套。
- **部署**：新部署按 `deploy/README.md` 单实例 Runbook 执行，无双 profile 分支；后端 `DEPLOYMENT_PROFILE` 移除见姊妹提案 `slim-backend-external-only`，前端双产物构建移除见 `slim-frontend-external-only`。
- **文档**：实现完成后在 `CHANGELOG.md` 追加 deploy 切除摘要并归档本 change。

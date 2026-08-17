# external-only-platform

AgentHub 收敛为纯对外智能体平台：单一 external 部署形态，无 deployment profile，无 internal 代码、路由、handler 与依赖。

## Purpose

落实 ADR-020：对内智能体平台已拆分到 Citadel，AgentHub 只保留 external 一种形态。本能力约束后端单形态注册、固定 Cookie 名、internal 依赖零回潮、前端单产物构建与 deploy 单实例部署模板；后端需求由 `slim-backend-external-only`、前端需求由 `slim-frontend-external-only`、deploy 需求由 `slim-deploy-single-instance` 归档时并入本文件，三个姊妹 change 已全部归档。

## Requirements

### Requirement: 单部署形态

AgentHub 只有一种部署形态，不区分 deployment profile。系统 MUST 不注册 internal 路由，MUST 不引入任务型 Agent handler，MUST 不依赖对象存储与文件解析 integration。

#### Scenario: external 部署不暴露 internal 路由

- WHEN 后端启动
- THEN `/api/v1/internal/*` 路由不存在（返回 404）
- AND 不存在 `DEPLOYMENT_PROFILE` 环境变量解析或 `DeploymentProfile` 枚举

#### Scenario: AgentType 只含 QA

- WHEN 查看 `AgentType` 枚举
- THEN 只包含 `QA` 一个值
- AND 不存在 `CONTRACT_REVIEW`、`RISK_ASSISTANT`、`REPORT_EXTRACTION`、`DOCUMENT_WRITING`

### Requirement: 固定 Cookie 名

认证 Cookie 名与 embed Cookie 名 MUST 固定，不按 profile 切换。

#### Scenario: Cookie 名固定

- WHEN 后端配置加载
- THEN auth Cookie 名为 `agenthub_session`
- AND embed Cookie 名为 `agenthub_embed_session`
- AND 不存在按 profile 选择 Cookie 名的逻辑

### Requirement: 不引入 internal 依赖

后端 MUST 不依赖 pymupdf、python-docx、langgraph、openpyxl、boto3、redis、arq。

#### Scenario: 无 internal 依赖 import

- WHEN 对 `backend/app/` 执行 grep
- THEN `import fitz`、`import docx`、`import boto3`、`from langgraph`、`import redis`、`import arq` 零命中

### Requirement: 前端单产物构建

前端 MUST 只产生一个构建产物 `dist`，MUST 不区分 external/internal，MUST 不使用 `__INTERNAL_BUILD__` 编译期常量。

#### Scenario: 单产物构建

- WHEN 执行 `npm run build`
- THEN 产物位于 `frontend/dist`
- AND 不存在 `frontend/dist/external` 或 `frontend/dist/internal`
- AND 构建产物不含 `ContractReviewPage`、`RiskAssistantPage`、`InternalLayout`

### Requirement: 单实例部署模板

`deploy/` MUST 只保留单实例部署模板，MUST 不包含双 profile 部署脚手架（profiles 目录、双 profile 脚本、双 systemd unit、双 nginx 配置、双 profile 备份与验证产物）。

#### Scenario: deploy 目录只含单实例模板

- WHEN 查看 `deploy/` 目录
- THEN 只存在单实例模板文件（`README.md`、`nginx/agenthub.conf`、`systemd/agenthub-backend.service`、`logrotate/agenthub`、`backup/mysql_backup.sh`、`backup/mysql_backup.cron`、`hosts.example`）
- AND 不存在 `profiles/`、`scripts/`、`verification/` 目录
- AND 不存在双 profile 的 systemd/nginx/backup/logrotate 变体与双 profile 部署文档

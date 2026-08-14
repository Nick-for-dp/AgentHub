## Context

AgentHub 后端代码仍停留在双 profile 形态：通过 `DEPLOYMENT_PROFILE` 环境变量区分 external/internal，`api/v1/router.py` 条件注册 `/api/v1/internal/*` 路由，`core/config.py` 按 profile 选 Cookie 名，`core/enums.py` 定义 `DeploymentProfile` 枚举与 `AgentType.CONTRACT_REVIEW`/`RISK_ASSISTANT`。internal 代码（`modules/contract_review/`、`modules/risk_assessment/`、`modules/file_parse/`、`modules/file_upload/`、`integrations/file_reader/`、`integrations/object_storage/`、`integrations/document_extraction/`、`integrations/langgraph_checkpoint/`、`modules/agent/task_handlers/`、`workers/`）约占后端 1.6 万行 / 130 文件。Alembic 有 7 个迁移（1 initial 建 16 张共用表 + 6 个 internal 增量建 7 张 internal 表）。

文档层（Phase 4）已由架构师重写为 external-only target 状态（ADR-020、Archi.md 去 internal 章节、Agent.md 红线精简、PLAN-internal.md 删除、OpenSpec internal 残留清除）。本设计收口后端代码层切除；前端与 deploy 切除分别见姊妹提案 `slim-frontend-external-only` 与 `slim-deploy-single-instance`。

Citadel 已独立承接全部 internal 能力（合同审查 LangGraph 重写、风控助手平移、file_reader、object_storage 等），代码切除不会丢失能力。本地 internal 资产已备份到 `D:\wukeh\work\projects\AgentHub-internal-archive\`。

当前代码基线（2026-08-14 GGBond 确认）：测试全绿（498 passed, 2 skipped），功能可用。

关心的红线（Agent.md §4/§5、DECISIONS ADR-001~014/020）：
- Dify 调用只在 `backend/app/integrations/dify`；本提案不改动 dify/audio 两个保留的 integration。
- 权限默认拒绝；`AuthenticatedSubject` 统一主体模型不变。
- 每次 Agent runtime 调用必须有 `agent_invocation_record`；快照三段 `retrieval`/`model`/`runtime` 不变。
- 产业互联网 iframe embed 一次性 token 协议不变。
- ADR-013：MySQL 8、UUIDv7 主键、UTC 存储 + 北京时间序列化、`TEST_DATABASE_URL` 显式配置。

## Goals / Non-Goals

**Goals:**
- 后端 internal 代码全量切除，共享文件掏空 internal 分支，external 主链路（登录/问答/会话/线索/embed/语音/管理端/分析）行为不变。
- Alembic 迁移链坍缩为单一 initial（16 张共用表），无 internal 表。
- 后端 `DEPLOYMENT_PROFILE` 机制彻底移除（枚举/配置/条件注册）。
- 依赖精简：移除 boto3、redis、langgraph、openpyxl、python-docx、pymupdf。
- external 测试全绿，grep 守卫确认无 internal 残留 import。

**Non-Goals:**
- 不改动 external 业务逻辑（问答 handler、线索收集、embed、语音、管理端）。
- 不改动 `integrations/dify/`、`integrations/audio/` 内部实现。
- 不改 `agent_invocation_record` 快照结构与 SSE 事件契约。
- 不引入新依赖、新能力、新表。
- 不处理 `.codex_tmp/`、`tmp/docs/`、`tmp/pdfs/` 等与平台功能无关的本地产物（已 gitignore）。
- 不回填 external 生产数据（当前全新建库，ADR-013/ADR-020）。
- 前端 internal 文件与双产物构建切除（姊妹提案 `slim-frontend-external-only`）。
- deploy 双 profile 模板切除（姊妹提案 `slim-deploy-single-instance`）。

## Decisions

### D1. 迁移链坍缩为单一新 initial，不保留历史迁移

当前 7 个迁移中，6 个 internal 增量建了 7 张 internal 表（`file_parse_task`、`contract_review_task`、`risk_assessment_task`、`risk_assessment_document`、`risk_review_event`、`risk_graph_checkpoint`、`contract_rule_set`/`contract_rule`）。切除后这些表不再需要。

方案：删除全部 7 个迁移文件，基于切除后的 SQLAlchemy 模型（只含 16 张共用表）重新生成单一 initial migration。external 生产库为全新建库无历史数据（ADR-013/ADR-020），无需数据迁移或 drop 脚本。

替代方案考虑过：保留 7 个迁移 + 追加 drop internal 表迁移。否决理由：internal 表从未在 external 生产库使用，保留历史迁移只增加认知负担；坍缩为单一 initial 更干净，符合 ADR-013「预留对象按 YAGNI 删除」精神。

执行顺序：先删除 internal 模型注册（`db/models.py`）与 internal 模块，再删全部迁移文件，最后用 `alembic revision --autogenerate` 生成新 initial 并人工校验只含 16 张表。迁移坍缩与模型切除必须原子完成：模型只注册 16 张表而迁移仍建 23 张表时 `alembic check` 必然漂移，两者不可拆分到不同变更。

### D2. DEPLOYMENT_PROFILE 彻底移除，Cookie 名固定

`DeploymentProfile` 枚举、`settings.deployment_profile` 字段、`core/config.py` 按 profile 选 Cookie 名逻辑全部删除。Cookie 名固定为 `agenthub_session`，embed Cookie 名固定为 `agenthub_embed_session`。`embed_enabled` 默认 true（external 本就开启）。

`api/v1/router.py` 的 internal 条件注册块删除，external 路由无条件注册。`scripts/seed.py` 删除 `--profile` 参数与 internal 分支，只初始化 external 资源。

替代方案考虑过：保留 `DEPLOYMENT_PROFILE` 但只支持 external。否决理由：留下死代码和认知负担，不符合本次瘦身目标；统一 `AuthenticatedSubject` 已覆盖两类访问方式，部署形态开关与鉴权能力无关。

### D3. 枚举精简：只保留 QA，删除死枚举值

`AgentType` 删除 `CONTRACT_REVIEW`、`RISK_ASSISTANT`（internal），同时删除 `REPORT_EXTRACTION`、`DOCUMENT_WRITING`（无 handler 注册的规划值，YAGNI）。`OperationType` 同步删除对应值。`Agent.type` 默认 `QA` 保持不变。

`AgentCreate` schema 暴露 `AgentType`：瘦身后只剩 `QA` 一个值，字段保留但枚举收紧，不破坏现有 API 契约。

### D4. 依赖精简：boto3/redis 移出主依赖，internal extra 整删

`pyproject.toml` 主依赖删除 `boto3`（仅 object_storage 用）、`redis`（app 代码无 import，仅 config 残留配置项）。`internal` optional dependency group 整体删除（`langchain-core`、`langgraph`、`openpyxl`、`python-docx`、`pymupdf`）。

`uv sync` 后 `uv.lock` 重建。external 链路无 import 这些包，删除安全。

## Risks / Trade-offs

- [迁移坍缩可能遗漏表或字段] -> 新 initial 生成后人工对照 ADR-013 的 16 张表清单校验；`alembic check` 确认模型与迁移不漂移；空库 `alembic upgrade head` 验证建表成功。
- [共享文件掏空可能误删 external 逻辑] -> `router.py`/`config.py`/`enums.py`/`seed.py` 改动逐文件 review；external 测试（profile/cookie/seed 相关测试需更新而非全删）作回归基线。
- [删除 internal 测试可能误删共享测试] -> 按 explore 盘点清单逐文件确认归属；`test_internal_router.py`、`test_profile_cookie_isolation.py`、`test_profile_seed.py` 需改写为 external-only 断言或删除；`test_config.py` 是混藏共享文件（约 17 个 internal/profile 用例 import 了待删模块），必须掏空而非整删，否则测试收集直接失败。
- [依赖删除可能遗漏间接引用] -> 删除后 `uv sync` + `uv run pytest` + grep 守卫（`fitz`/`docx`/`boto3`/`langgraph`/`arq`/`redis` import 零残留）。
- [Citadel 可能仍引用 AgentHub 代码] -> Citadel 已独立演进（单向只读参考），不反向依赖 AgentHub；删除安全。

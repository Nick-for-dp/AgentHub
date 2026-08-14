## Why

`DECISIONS.md` ADR-020 已决策：AgentHub 原同时承载对外（external）和对内（internal）智能体平台，对内部分（合同审查、风控助手、file_reader、object_storage/MinIO、file_parse、内部路由、arq/Redis、PaddleOCR/Qwen、LangGraph checkpoint 等）已单向抽离到独立项目 Citadel。AgentHub 收敛为纯对外智能体平台。

本文档对应 PLAN.md 之外的新增执行事项：ADR-020 代码层落地的 Phase 1（后端切除），瘦身阶段划分见 `ag.md` §5。姊妹提案：`slim-frontend-external-only`（Phase 2，前端切除）、`slim-deploy-single-instance`（Phase 3，deploy 切除）。三者技术解耦，可独立评审、独立验证、独立回滚。

文档体系（Phase 4）已由架构师重写为 target 状态：`Archi.md` 移除了部署 profile、内部链路与文件解析章节；`DECISIONS.md` 新增 ADR-020 并移除 ADR-015~019；`Agent.md` 红线删去 internal 相关条目；`PLAN-internal.md` 已删除；OpenSpec internal changes/specs 已清除。但**后端代码仍停留在双 profile 形态**——约 130 个 internal 文件 / 1.6 万行、6 个 internal 迁移仍留在仓库。本提案收口后端代码层的切除与迁移链坍缩，使后端代码事实与文档事实对齐。

现在做是因为：文档已声明 external-only，代码滞后会造成认知分裂；internal 代码引入的依赖（pymupdf、python-docx、langgraph、openpyxl、boto3、redis）对纯对外平台是无谓负担。当前代码基线（2026-08-14 GGBond 确认）：测试全绿（498 passed, 2 skipped），功能可用。

## What Changes

### 后端切除

- 整目录删除：`modules/contract_review/`、`modules/risk_assessment/`、`modules/file_parse/`、`modules/file_upload/`、`integrations/file_reader/`、`integrations/object_storage/`、`integrations/document_extraction/`、`integrations/langgraph_checkpoint/`、`api/v1/endpoints/internal/`、`modules/agent/task_handlers/`、`workers/`（空壳）。
- 删除 internal 专用脚本：`scripts/contract_review_compare_workflows.py`、`contract_review_mvp_demo.py`、`risk_document_extraction_smoke.py`、`risk_graph_checkpoint_spike.py`。
- 删除 internal 相关测试（约 32 个文件）。
- Alembic 迁移链坍缩：删除全部 7 个迁移（1 initial + 6 internal 增量），重写为单一 initial migration，只建 16 张共用表。
- 掏空共享文件：`api/v1/router.py`（删 internal 条件注册）、`db/models.py`（删 internal 模型注册）、`core/enums.py`（删 `DeploymentProfile`、`AgentType`/`OperationType` 的 internal 值与无 handler 的 `REPORT_EXTRACTION`/`DOCUMENT_WRITING` 死枚举）、`core/config.py`（删 `deployment_profile`、`redis_url`、internal 配置块、双 Cookie 名逻辑，Cookie 名固定）、`scripts/seed.py`（删 `--profile` 与 internal 分支）、`pyproject.toml`（删 boto3、redis 主依赖与整个 internal extra）、`.env.example`（删 `DEPLOYMENT_PROFILE` 与 internal 专用配置项）。

### DEPLOYMENT_PROFILE 机制移除（后端）

后端 `DEPLOYMENT_PROFILE` 环境变量、`DeploymentProfile` 枚举、profile-aware Cookie 名、条件路由注册全部删除。Cookie 名固定为 `agenthub_session`，embed Cookie 名固定为 `agenthub_embed_session`。统一 `AuthenticatedSubject` 架构不变（覆盖账号密码登录、iframe embed、API Key 三类访问方式）。前端侧 `VITE_DEPLOYMENT_PROFILE`、`__INTERNAL_BUILD__` 编译期常量与双产物构建的移除由姊妹提案 `slim-frontend-external-only` 收口。

## Capabilities

### New Capabilities

- `external-only-platform`：新增「单部署形态」「固定 Cookie 名」「不引入 internal 依赖」三条验收需求（切除性变更的规格固化，external 业务行为不变）。该能力的「前端单产物构建」需求由姊妹提案 `slim-frontend-external-only` 补充，归档时合并。

### Modified Capabilities

- `agent-handler-dispatch`：移除 `TaskHandler` / `TaskHandlerRegistry` 相关描述，只保留 `ChatHandler` / `ChatHandlerRegistry` 对话流分发（该 spec 已在 Phase 4 从 `openspec/specs/` 中删除 `agent-task-handler-dispatch`，本提案在代码层落实）。
- `chat-postprocessors`：不受影响，保持现状。

## Impact

- **受影响代码**：后端约 130 个文件删除 + 7 个共享文件掏空。
- **受影响 API**：`/api/v1/internal/*` 路由整体移除（已在 `router.py` 条件注册，external 部署本就不暴露）；external API（`/auth/*`、`/chat/*`、`/conversations/*`、`/embed/*`、`/audio/*`、`/admin/*`）行为不变。
- **数据库**：迁移链从 7 个坍缩为 1 个新 initial；internal 表（`file_parse_task`、`contract_review_task`、`risk_assessment_task`、`risk_assessment_document`、`risk_review_event`、`risk_graph_checkpoint`、`contract_rule_set`/`contract_rule`）不再建表。external 16 张共用表结构不变。当前为全新建库无历史数据迁移（ADR-013/ADR-020）。
- **依赖**：移除 `boto3`、`redis`（主依赖）、`langchain-core`、`langgraph`、`openpyxl`、`python-docx`、`pymupdf`（internal extra 整体删除）。
- **测试**：删除约 32 个 internal 测试文件（206 个用例，占全套 41%）+ 掏空 `test_config.py` 的 internal/profile 用例（约 17 个）后，剩余 external 测试（约 280 个）必须全绿（对照 pre-slimming 基线 498 passed, 2 skipped，无新增失败）；同步合并少量重复用例（TestAdminPermission 与 assert_allowed 同路径重复、_build_safe_inputs 等价类、SSE 脱敏参数化，约 12 个），只合并不裸删，行为覆盖不缩水；需补 grep 守卫测试确认无 `fitz`/`docx`/`boto3`/`langgraph`/`DEPLOYMENT_PROFILE` 残留 import。
- **文档**：Phase 4 已完成文档重写，本提案不重复改文档；实现完成后只需在 `CHANGELOG.md` 追加后端切除摘要并归档本 change。
- **部署**：`seed.py` 不再接受 `--profile` 参数；deploy 双 profile 模板切除由姊妹提案 `slim-deploy-single-instance` 收口。

## 1. 后端 internal 模块与 integration 切除

- [x] 1.1 删除 `backend/app/modules/contract_review/`（22 文件）
- [x] 1.2 删除 `backend/app/modules/risk_assessment/`（54 文件）
- [x] 1.3 删除 `backend/app/modules/file_parse/`（5 文件）
- [x] 1.4 删除 `backend/app/modules/file_upload/`（3 文件）
- [x] 1.5 删除 `backend/app/modules/agent/task_handlers/`（4 文件：`__init__.py`、`contract_review.py`、`risk_assessment.py`、`pipeline.py`）
- [x] 1.6 删除 `backend/app/integrations/file_reader/`（13 文件）
- [x] 1.7 删除 `backend/app/integrations/object_storage/`（5 文件）
- [x] 1.8 删除 `backend/app/integrations/document_extraction/`（6 文件）
- [x] 1.9 删除 `backend/app/integrations/langgraph_checkpoint/`（3 文件）
- [x] 1.10 删除 `backend/app/api/v1/endpoints/internal/`（5 文件：`__init__.py`、`files.py`、`file_parse.py`、`contract_review.py`、`risk_assistant.py`）
- [x] 1.11 删除 `backend/app/workers/`（空壳，4 文件）
- [x] 1.12 删除 4 个 internal 脚本：`backend/scripts/contract_review_compare_workflows.py`、`contract_review_mvp_demo.py`、`risk_document_extraction_smoke.py`、`risk_graph_checkpoint_spike.py`

## 2. 后端共享文件掏空

- [x] 2.1 `backend/app/api/v1/router.py`：删除 internal router import（`:20`）与条件注册块（`:123-143`，`if resolved_settings.deployment_profile == DeploymentProfile.INTERNAL`）；external 路由无条件注册
- [x] 2.2 `backend/app/db/models.py`：删除 internal 模型注册（ContractReviewTask、FileParseTask、RiskGraphCheckpoint、RiskAssessmentTask/Document、RiskReviewEvent，约 `:4-6`、`:11-15`）；确认保留 16 张共用表模型
- [x] 2.3 `backend/app/core/enums.py`：删除 `DeploymentProfile` 枚举（`:4-6`）；`AgentType` 删除 `CONTRACT_REVIEW`、`RISK_ASSISTANT`、`REPORT_EXTRACTION`、`DOCUMENT_WRITING`，只保留 `QA`；`OperationType` 同步删除对应 internal 值
- [x] 2.4 `backend/app/core/config.py`：删除 `deployment_profile` 字段（`:38`）、`redis_url`（`:46`）、internal 配置块（约 `:80-104`）、profile-aware Cookie 名逻辑（`:170-185`）；Cookie 名固定为 `agenthub_session`、embed Cookie 名固定为 `agenthub_embed_session`；`embed_enabled` 默认 true
- [x] 2.5 `backend/scripts/seed.py`：删除 `--profile` 参数与 internal 分支（`_seed_internal`、`_get_or_create_contract_review_agent`、`_get_or_create_risk_agent`、`SeedInputs` 中 contract_review_* 字段）；只保留 external seed 逻辑
- [x] 2.6 `backend/pyproject.toml`：主 dependencies 删除 `boto3`、`redis`；删除整个 `[project.optional-dependencies] internal` group（langchain-core、langgraph、openpyxl、python-docx、pymupdf）；运行 `uv sync` 重建 lockfile
- [x] 2.7 `backend/.env.example`：删除 `DEPLOYMENT_PROFILE` 及 internal 专用配置项（CONTRACT_REVIEW_*、RISK_DOCUMENT_*、MINIO_*、REDIS_URL 等）

## 3. Alembic 迁移链坍缩

- [x] 3.1 删除 `backend/app/db/migrations/versions/` 下全部 7 个迁移文件
- [x] 3.2 确认 `backend/app/db/models.py` 只注册 16 张共用表模型（org_unit、user_account、api_key、permission_policy、agent、knowledge_base、agent_knowledge_base、document、agent_invocation_record、auth_session、embed_session、conversation、conversation_message、lead_contact、sales_lead、lead_capture_event）
- [x] 3.3 运行 `uv run alembic revision --autogenerate -m "initial_schema_mysql"` 生成新 initial；人工校验只含 16 张表、UUIDv7 主键、生成列 `external_phone_uk`、utf8mb4
- [x] 3.4 空库验证：`uv run alembic upgrade head` 成功建表；`uv run alembic check` 无漂移

## 4. 后端测试清理与更新

- [x] 4.1 删除 internal 相关测试（约 32 文件）：`test_contract_review_*`、`test_risk_*`、`test_file_parse_*`、`test_file_upload_*`、`test_object_storage_*`、`test_docx_reader.py`、`test_pdf_reader.py`、`test_image_reader.py`、`test_task_handler_dispatch.py`、`test_risk_sample_file_package.py`（integration）
- [x] 4.2 改写 profile 机制测试：`test_internal_router.py` 改为断言 external 不注册 `/internal/*`（或删除）；`test_profile_cookie_isolation.py` 删除（无 profile）；`test_profile_seed.py` 改为断言 seed 无 `--profile` 参数
- [x] 4.3 掏空共享测试 `test_config.py`：删除 internal import（`integrations/document_extraction`、`modules/risk_assessment.extraction.provider_factory`）与全部 risk_document_provider / object_storage 默认值用例（约 14 个）；profile 用例改写——`test_external_profile_keeps_compatible_cookie_defaults` 改为断言固定 Cookie 名 `agenthub_session` / `agenthub_embed_session` 且 `embed_enabled` 默认 true，`test_internal_profile_uses_isolated_cookie_defaults_and_disables_embed` 删除，`test_cookie_names_can_be_overridden_per_instance` 去除 `deployment_profile` 入参；保留生产密钥校验、Cookie 名合法性校验、embed origin 解析、CORS / frame-ancestors 用例（约 12 个）
- [x] 4.4 确认 `conftest.py` 无 internal 引用（已确认干净，复核一遍）
- [x] 4.5 补 grep 守卫测试：assert 全代码无 `import fitz`、`import docx`、`import boto3`、`from langgraph`、`import redis`、`DEPLOYMENT_PROFILE`、`DeploymentProfile` 残留
- [x] 4.6 external 测试去重（合并等价类，行为断言一条不丢）：① `test_auth_service.py` 删 `TestAdminPermission` 4 个与 `TestAssertAllowed` 同路径的重复用例，若评审确认 `require_admin_permission` 装配无覆盖则补 1 个真实装配测试；② `test_agent_runtime.py` `TestBuildSafeInputs` 删 `test_removes_dify_api_key_from_inputs`（被 removes_all 覆盖）与 `test_empty_config_returns_empty_dict`（与 None 同路径），5→3；③ `TestExtractAPIKey` 两个 None 路径合并为 parametrize，3→2；④ `test_dify_client.py` `TestDifyClientHTTPStatusError` 三个错误体脱敏用例 parametrize 合并并抽公共 mock helper（保留 ResponseNotRead 用例独立），4→2；⑤ `TestSanitizeSSELineForLog` 的 DONE/keepalive/非JSON/空 data 四个"原样保留"用例合并为 1 个 parametrize，9→6

## 5. 验证

- [x] 5.1 后端：`cd backend && uv sync && uv run pytest` 全绿（pre-slimming 基线：498 passed, 2 skipped，2026-08-14 GGBond 确认测试全绿、功能可用；切除 internal 测试后通过数会下降，但剩余 external 测试必须全绿，无新增失败）
- [x] 5.2 后端：`uv run ruff check .` 无错
- [x] 5.3 后端：空库 `uv run alembic upgrade head` 成功；`uv run alembic check` 无漂移
- [x] 5.4 后端 grep 守卫：`fitz`、`docx`、`boto3`、`langgraph`、`openpyxl`、`arq`、`import redis`、`DEPLOYMENT_PROFILE`、`DeploymentProfile`、`task_handlers`、`/api/v1/internal` 零残留
- [x] 5.5 冒烟：`uvicorn app.main:app` 启动无 import 错误
- [x] 5.6 `CHANGELOG.md` 追加后端切除摘要；归档本 change 到 `openspec/specs/`

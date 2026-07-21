## 1. 业务口径、类型校验策略与 LangGraph spike

- [x] 1.1 新建 `docs/risk-assistant/audit-field-policy-v1.md`，逐项定义一期审计字段代码、中文名称、展示顺序、来源文档类型、单位、关键级别和缺件处理；业务模式仅定义为审批样表原文字段
- [x] 1.2 新建 `docs/risk-assistant/document-type-validation-v1.md`，为四类文档定义 expected/conflicting 标题与结构标记、MATCHED/SUSPECTED/UNVERIFIED 判定、文件名弱提示规则和版本号
- [x] 1.3 在 `DECISIONS.md` 新增 LangGraph 单图 interrupt/resume ADR，明确外层 TaskHandler、内层图、完整复核上下文、内容级类型校验和不使用自由 ReAct
- [x] 1.4 在 `backend/scripts/risk_graph_checkpoint_spike.py` 实现 MySQL checkpointer 最小 interrupt/resume，验证同一 thread/checkpoint 跨请求恢复且不接正式路由
- [x] 1.5 将 LangGraph/LangChain 加入 `backend/pyproject.toml` internal optional dependencies，更新锁文件并运行 external profile import smoke test

## 2. 原始文件名、数据模型、迁移与 API schema

- [x] 2.1 修改 `FileParseTaskCreate`、`FileParseTaskRead` 和 `FileParseTask` model，增加 original_filename；新建请求必填，存量数据库行允许为空
- [x] 2.2 在 FileParseService 规范化 original_filename 为 basename，校验非空、长度和扩展名与 source_uri 对象类型一致；添加 Windows/Unix 路径和冲突扩展名测试
- [x] 2.3 在文件解析完成后用持久化 original_filename 覆盖随机临时文件名产生的 ParsedDocumentV1.metadata.filename；测试 result_snapshot 和查询响应一致
- [x] 2.4 修改前端 `createFileParseTask` 类型和请求参数，把 upload prepare 返回的 original_filename 原样传入解析任务
- [x] 2.5 更新合同审查工作台 composable、前端 API mock 和后端 file-parse endpoint 测试，证明既有上传→解析→合同审查链路继续通过
- [x] 2.6 修改 `backend/app/core/enums.py`，增加 RISK_ASSISTANT、RISK_ASSESSMENT、风险任务状态及 MATCHED/SUSPECTED/UNVERIFIED 文档类型校验状态；更新枚举序列化测试
- [x] 2.7 新建 `modules/risk_assessment/models.py` 的 RiskAssessmentTask，包含 owner、business_code、status、graph thread/checkpoint、invocation、versions、当前/最终 result_snapshot、error 和时间戳
- [x] 2.8 在同文件增加 RiskAssessmentDocument，关联 task 与 file_parse_task，保存 original_filename 快照、declared type、order、type validation status/warnings 和 extraction_snapshot
- [x] 2.9 在同文件增加 RiskReviewEvent，保存 target_kind=FIELD/DOCUMENT_TYPE、target_code、before/alternatives、after/确认动作、reason、actor、sources、checkpoint version 和时间
- [x] 2.10 新建 `integrations/langgraph_checkpoint/models.py` 或等价 checkpoint model，保存 thread、checkpoint、version、恢复所需 ID、受影响字段和 next node，不保存完整 OCR/ParsedDocument
- [x] 2.11 生成单一 Alembic migration：为 file_parse_task 增加 nullable original_filename，并创建四张风控表、外键和 owner/status 索引；执行 upgrade→downgrade→upgrade
- [x] 2.12 新建 `modules/risk_assessment/repository.py`，分别实现 task/document/review/checkpoint 查询写入；用真实测试数据库验证 owner/status、来源文件快照和 checkpoint version 冲突
- [x] 2.13 新建 `modules/risk_assessment/schemas.py`，定义 create/read/result/review_context/review submit schema；测试响应包含 original_filename 但不暴露 checkpoint 原始 state

## 3. TaskHandler 暂停与恢复扩展

- [x] 3.1 在 `modules/agent/task_handlers/pipeline.py` 增加 `ExecutionOutcome`/`SuspendedResult`，保持现有 CoreResult/PostprocessResult API 兼容
- [x] 3.2 在 `modules/agent/task_handlers/__init__.py` 增加可选 `finalize_suspended()` 钩子；默认实现明确报不支持且不影响现有 handler
- [x] 3.3 为 TaskHandler 增加 `resume(ctx, resume_payload)` 模板入口，复用 prepare/归属校验但不重复 begin invocation
- [x] 3.4 修改 `modules/invocation/service.py`，增加更新未终态 runtime snapshot 的方法；测试 WAITING_REVIEW 不写 finished_at 或 SUCCEEDED
- [x] 3.5 扩展 `test_task_handler_dispatch.py`，覆盖 suspended outcome 不调用 success/failure finalize
- [x] 3.6 扩展 `test_contract_review_handler.py`，证明合同审查成功/失败路径和 invocation 数量保持不变

## 4. 声明文档类型的内容级校验

- [x] 4.1 新建 `modules/risk_assessment/extraction/document_type_validation.py`，实现版本化纯函数 validator，输入 declared type、original filename 和统一 anchored blocks，输出 MATCHED/SUSPECTED/UNVERIFIED 及稳定 reason codes
- [x] 4.2 为 validator 添加参数化测试，覆盖预期标记、冲突标记、两类标记并存、无标记、大小写/空白/全半角归一化和“客户供货协议.pdf”等非标准文件名
- [x] 4.3 调整 DocumentExtractionProvider 临时协议，使 provider 可返回字段字典及稳定类型校验 warning；不得返回或持久化完整 OCR 文本、provider 原始响应或额外领域对象
- [x] 4.4 修改 PaddleOCR+Qwen provider：DOCX 使用 ParsedDocument blocks，扫描件在同一次 PaddleOCR 产生 OcrDocument 后运行 validator，再调用一次 Qwen
- [x] 4.5 添加 provider 调用次数测试，断言扫描件类型校验后仍只调用一次 PaddleOCR 和一次 Qwen，普通 DOCX 仍不调用 PaddleOCR
- [x] 4.6 更新 fake provider、provider contract tests 和 extraction service，合并 DOCUMENT_TYPE_SUSPECTED/UNVERIFIED；仅 SUSPECTED 使有值字段统一变为 UNCERTAIN
- [x] 4.7 扩展 `test_risk_document_extraction.py`，覆盖内容冲突不切换 extractor、内容一致但文件名非标准、正文无法验证和原始文件名进入 provider
- [x] 4.8 添加安全回归测试，确保类型校验日志、warnings 和 DocumentExtractionResult 不包含完整 OCR、文件字节、Base64、签名 URL 或模型推理文本

## 5. 审计字段规范化与确定性规则

- [x] 5.1 新建 `modules/risk_assessment/audit_catalog.py`，加载 1.1 的字段代码、名称、顺序、来源和关键级别；测试目录稳定且包含 MISSING 字段展示位置
- [x] 5.2 新建 `rules/normalization.py`，读取第一阶段 ExtractedField 并实现金额、重量、单位、日期、合同号和公司名称规范化；添加纯函数测试
- [x] 5.3 新建 `rules/field_resolver.py`，使用字段值、sources 和 alternatives 形成 accepted/rejected/unresolved 业务事实；测试不会丢弃 alternatives
- [x] 5.4 新建 `rules/contract_amount.py`，实现数量×含税单价=含税金额规则；测试 5350/5850 示例和容差边界
- [x] 5.5 新建 `rules/payment_ratio.py`，实现 85% 预付款、15% 保证金金额勾稽；测试金额和舍入容差
- [x] 5.6 新建 `rules/settlement.py`，实现结算数量×销售单价、浮动费差额等已确认规则；未确认口径返回 NOT_APPLICABLE
- [x] 5.7 新建 `rules/timeline.py`，实现采购、销售、交货和结算日期顺序；测试缺日期不产生伪差异
- [x] 5.8 新建 `rules/criticality.py`，加载字段关键级别；测试 critical unresolved 生成 review item、non-critical 生成 warning
- [x] 5.9 定义 rule_code/version/input_evidence/outcome 规则结果 schema，并在各规则测试中断言审计字段完整
- [x] 5.10 实现业务模式原文透传：只保留 ApprovalFormExtractor 的 raw value/status/sources，不生成 code 或 mapping status，也不因缺少枚举生成 review item；原文字段自身状态仍进入通用 criticality 判断

## 6. LangGraph state、checkpoint 与领域节点

- [x] 6.1 新建 `modules/risk_assessment/graph/state.py`，定义轻量 RiskGraphState 和 graph schema version；测试 state 不包含完整 ParsedDocument、OCR 文本或 review_context
- [x] 6.2 新建 `integrations/langgraph_checkpoint/mysql.py`，按 spike 实现 put/get/list checkpoint 和 version 冲突；添加 MySQL 集成测试
- [x] 6.3 新建 `graph/nodes/load_file_parse_results.py`，校验关联 file_parse_task 的 owner、SUCCEEDED、original_filename、declared type 和 ParsedDocument schema version；缺少原始文件名时 fail closed
- [x] 6.4 新建 `graph/nodes/extract_documents.py`，调用第一阶段 extraction service，把 DocumentExtractionResult、original_filename 和 declared type 保存到 RiskAssessmentDocument；测试每份文件每次普通执行只抽取一次
- [x] 6.5 新建 `graph/nodes/validate_declared_document_types.py`，把 SUSPECTED 转为关键复核信号、UNVERIFIED 转为 warning，并保存紧凑 type validation snapshot；不得按文件名或内容自动切换 extractor
- [x] 6.6 新建 `graph/nodes/normalize_and_resolve_fields.py`，规范化 ExtractedField 并输出 document facts/unresolved；保留通用 `fact_enrichers` 扩展点
- [x] 6.7 新建 `graph/nodes/run_document_checks.py`，顺序运行规则注册表并输出 checks、warnings 和 review signals；保留 `comparison_steps` 扩展点
- [x] 6.8 新建 `graph/nodes/build_review_items.py`，分别生成 FIELD 和 DOCUMENT_TYPE review items；类型冲突项必须带 original_filename、declared type 和 warning，业务模式没有枚举不得触发
- [x] 6.9 新建 `graph/nodes/materialize_result_snapshot.py`，按 audit catalog 组装全部字段、original_filename、declared type、type validation、sources、alternatives、checks、warnings、review items 和 `is_review_target`
- [x] 6.10 为 result snapshot 添加测试：WAITING_REVIEW 时展示非冲突/MISSING 字段及来源文件原始名称，且只有 review targets 可编辑
- [x] 6.11 新建 `graph/nodes/route_review.py`，无未解决 critical 项时继续 finalize，有未解决项时 interrupt 并持久化 WAITING_REVIEW
- [x] 6.12 新建 `graph/nodes/finalize_document_result.py`，输出 schema/parser/extractor/type-validation/rule/graph versions、audit items、facts、checks、warnings 和总体状态
- [x] 6.13 新建 `graph/nodes/apply_human_review.py`，仅从 review event ID 加载决定；字段复核标记受影响字段，类型复核只接受确认当前声明并解除 type-only uncertainty，拒绝修改非 review target 或在同一 thread 改类型
- [x] 6.14 新建 rerun 节点，只重新运行受影响规则并重新物化 result snapshot；若仍有未解决 critical 项则再次路由复核，不重复 OCR/抽取
- [x] 6.15 新建 `graph/builder.py`，连接自动完成和 interrupt→resume 两条确定性路径；用 fake graph 测试节点顺序
- [x] 6.16 新建 `test_risk_graph.py`，覆盖自动 SUCCEEDED、类型 SUSPECTED、WAITING_REVIEW、完整复核上下文和非 review target 只读
- [x] 6.17 扩展 `test_risk_graph.py`，覆盖跨请求 resume、旧 checkpoint 冲突、多轮复核、取消后不可恢复和恢复时不重复抽取

## 7. RiskAssessmentTaskHandler 与领域服务

- [x] 7.1 新建 `modules/agent/task_handlers/risk_assessment.py`，实现 prepare/begin 并保证每次首次执行只创建一个 invocation
- [x] 7.2 在 handler 实现 core 调用 graph executor、suspended 持久化和 success/failure/cancel finalize
- [x] 7.3 修改 TaskHandlerRegistry 注册 RISK_ASSISTANT 工厂；扩展 dispatch 测试覆盖每次新实例且不回退 QA/CONTRACT_REVIEW
- [x] 7.4 新建 `modules/risk_assessment/service.py` 的 create_task，校验 Cookie subject、文件归属、业务编号、文档类型和 file_parse_task.original_filename；名称必须从解析任务复制
- [x] 7.5 在 service 实现 get_task，将 result_snapshot 投影为普通结果或 WAITING_REVIEW 的 review_context；校验来源文件名、声明类型、类型校验 warning 和只读/可编辑标记
- [x] 7.6 在 service 实现 execute，仅允许 PENDING 且 Agent type 正确；测试重复 execute 不新增 invocation
- [x] 7.7 在 service 实现 submit_review，要求 WAITING_REVIEW、当前 FIELD/DOCUMENT_TYPE review item、reason 和 checkpoint version；测试只读字段拒绝、类型原地改写拒绝及并发提交一个成功一个 409
- [x] 7.8 在 service 实现 cancel，分别处理 PENDING/RUNNING/WAITING_REVIEW；测试 invocation 以 USER_CANCELLED 收口

## 8. Internal API、seed 与验收

- [x] 8.1 新建 `api/v1/endpoints/internal/risk_assistant.py` 的 POST tasks 和 GET task；GET 在 WAITING_REVIEW 返回带原始文件名和类型校验状态的完整 review_context
- [x] 8.2 在同 endpoint 增加 execute/reviews/cancel，并复用 `get_current_subject`、稳定错误码和 request_id
- [x] 8.3 在 `api/v1/router.py` 条件注册 internal 路由；扩展 `test_internal_router.py` 验证 external profile 返回 404
- [x] 8.4 修改 `scripts/seed.py`，幂等创建 code=risk-assistant、type=RISK_ASSISTANT 的 internal Agent 和最小权限
- [x] 8.5 新建 `test_risk_assessment_service.py`，覆盖归属、缺失原始文件名拒绝、来源名称快照、类型校验、完整审计信息、invocation 和 review event
- [x] 8.6 新建 `test_risk_assistant_endpoint.py`，覆盖 401、403/越权、409、自动完成、类型冲突暂停、完整复核上下文和恢复 API
- [x] 8.7 运行文件上传/解析与合同审查定向回归，证明 file-parse 请求契约升级后既有 Web 工作台和 TaskHandler 路径不退化
- [x] 8.8 更新 `Archi.md`、`PLAN-internal.md`、`DECISIONS.md` 和 `CHANGELOG.md`，记录原始文件名数据流、类型校验优先级、状态机和业务模式延期边界
- [x] 8.9 运行 strict OpenSpec validate、变更范围 Ruff、前端相关测试和后端风控/TaskHandler 定向测试
- [x] 8.10 运行后端/前端全量测试、external profile import smoke test，并用四份真实文件验证非硬编码名称、一次 OCR/Qwen、自动完成或暂停恢复结果


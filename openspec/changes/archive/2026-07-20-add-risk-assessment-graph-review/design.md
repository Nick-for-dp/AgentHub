## Context

本 change 依赖 `add-risk-document-extraction-foundation` 交付的极简 DocumentExtractionResult/ExtractedField。它不改变 OCR/Qwen 的职责分工，而是在图执行时抽取多份文档，再形成跨文档业务事实、运行规则并处理人工复核。

现有上传接口返回 `original_filename`，但 file_parse 创建只接收随机化后的 `source_uri`，解析器又读取随机临时文件，因此生产环境的 ParsedDocument metadata 会丢失用户原始文件名。现有声明类型检查只扫描 metadata filename 和前三个 ParsedDocument block；扫描 PDF 的有效文字存在 PaddleOCR 结果中，这段检查无法看到，导致内容级冲突可能漏报。

现有 TaskHandler 固定走 preprocess→core→postprocess→success/failure，没有非终态暂停；`AgentType` 也没有 RISK_ASSISTANT。风控流程需要跨请求保留同一执行、同一 invocation 和人工决定，因此引入 LangGraph interrupt/checkpoint/resume，但保持 AgentHub 拥有任务和最终事实。

## Goals / Non-Goals

**Goals:**

- 建立多文件 risk_assessment_task 和 API 生命周期。
- 持久化规范化后的原始文件名，并在任务结果、审计证据和人工复核上下文中稳定显示。
- 以文档内容为主校验 declared_document_type；扫描件复用同一次 PaddleOCR 结果，不新增 OCR/VLM 调用。
- 用一张 LangGraph 图完成文档事实融合、确定性核对和人工复核。
- 关键冲突时 WAITING_REVIEW，提交人工决定后从同一 checkpoint 恢复。
- 人工复核时展示当前任务全部审计字段、状态、候选值、证据和核对结果，同时只允许修改待复核项。
- 记录任务、规则、checkpoint、人工事件和 invocation 审计。
- 保留审批样表抽取的业务模式原文和证据，为后续枚举映射预留通用扩展点。
- 给后续 ERP change 预留稳定的事实 enrichment/comparison 扩展点。

**Non-Goals:**

- 不更换或重新实现 PaddleOCR、Qwen 字段选择和四类 extractor；不接入 ERP，不建设正式前端和 Excel 导出。
- 不定义或猜测业务模式枚举、别名和映射规则；缺少枚举映射不作为本阶段复核触发条件，原文字段自身的 MISSING/UNCERTAIN 仍按通用关键级别策略处理。
- 不要求文件名精确等于“01X销售合同”等业务编号格式，不根据文件名自动分类，也不在校验冲突时自动切换 extractor。
- 不使用自由式 ReAct；自动复核为固定规则和人工决定后的局部重算。
- 不输出最终业务审批同意/否决，只输出文档核对状态。

## Decisions

### 1. TaskHandler 是外层，LangGraph 是内层

`RiskAssessmentTaskHandler` 管归属、状态、invocation 和持久化；`RiskAssessmentGraph` 管领域节点。图节点位于 `modules/risk_assessment/graph/`，endpoint 仅调用 service。

本阶段图为：

```text
load_file_parse_results
 -> extract_documents
 -> validate_declared_document_types
 -> normalize_and_resolve_fields
 -> run_document_checks
 -> build_review_items_and_snapshot
 -> route_review
      -> finalize_document_result
      -> interrupt -> apply_human_review -> rerun_affected_checks
                   -> build_review_items_and_snapshot -> route_review
```

在 `normalize_and_resolve_fields` 后预留 `fact_enrichers` 和 `comparison_steps` 扩展点，第三阶段 ERP 以注册节点接入，不改写已有节点契约。

### 2. 原始文件名进入 file parse 事实链

上传准备接口继续返回用户提交的 `original_filename`，对象存储 key 继续使用 UUID，避免业务名称进入存储路径。`POST /internal/file-parse/tasks` 改为提交 `{source_uri, original_filename}`；FileParseService 只保存 basename，剥离客户端路径片段，并拒绝空值或与对象扩展名不一致的文件名。解析完成后以持久化值覆盖临时文件名生成的 `ParsedDocument.metadata.filename`。

`file_parse_task.original_filename` 是后续业务任务的来源名称权威值。创建 RiskAssessmentDocument 时从 file_parse_task 复制快照，不接受风险任务请求再次传入名称，避免同一文件在不同层被任意改名。存量 file_parse_task 允许该列为空，但新的风险任务不得引用缺少原始文件名的存量解析任务。

### 3. 声明类型使用内容优先的确定性校验

调用方声明的 PURCHASE_CONTRACT/SALES_CONTRACT/APPROVAL_FORM/SETTLEMENT_STATEMENT 仍直接选择专用 extractor，不运行自动分类模型。文件名仅为弱提示，不匹配固定编号或完整名称。

每类 extractor 提供版本化 expected/conflicting 标题与结构标记。普通 DOCX/文本 PDF 使用 ParsedDocument blocks；扫描 PDF/图片由 production provider 在同一次 PaddleOCR 得到 OcrDocument 后运行同一纯函数 validator，再调用一次 Qwen。provider 临时返回字段字典和稳定校验 warning，DocumentExtractionService 合并 warning 后仍输出原有极简 DocumentExtractionResult，不持久化完整 OCR 文本或 provider 原始响应。

内容证据优先于文件名：明确冲突输出 `DOCUMENT_TYPE_SUSPECTED`，所有非空字段保持来源但标记 UNCERTAIN；没有足够类型标记时输出 `DOCUMENT_TYPE_UNVERIFIED`，不自动切换 extractor。LangGraph 的 `validate_declared_document_types` 将 SUSPECTED 作为关键复核信号，UNVERIFIED 作为 warning 随结果展示。人工若确认声明错误，MVP 通过取消并用正确类型重建任务处理，不在同一 graph thread 内自动重分类或重新抽取。

### 4. 人工复核属于同一 graph thread

`route_review` 对 unresolved critical review item 执行 interrupt。任务保存 `graph_thread_id/current_checkpoint/current_node`，状态置 WAITING_REVIEW；invocation 保持未完成并更新 `snapshot.runtime.execution_state`。`POST /reviews` 写 review event 后，以同一 thread 恢复。

恢复 payload 只包含 review event ID 和 checkpoint version，图从数据库加载决定；禁止前端传完整 graph state。并发提交使用 checkpoint version 乐观锁，第二个提交返回冲突。

每次 interrupt 前将当前审计结果投影到 task 的 `result_snapshot`。`GET /tasks/{id}` 在 WAITING_REVIEW 时返回 `review_context`：按审计字段目录展示所有字段的 FOUND/MISSING/UNCERTAIN、原始值、规范化值、单位、来源文件原始名称、声明类型、类型校验 warning、quote/page/bbox、alternatives、关联规则结果和 warning，并用 `is_review_target` 明确可编辑项。未进入 review items 的字段只读；`POST /reviews` 不接受任意字段批量覆盖。

### 5. TaskHandler 增加可选 suspend/resume 协议

通用 TaskHandler 新增可选 `finalize_suspended`/`resume` 扩展点或等价 outcome。合同审查不实现，仍走原三阶段终态。Risk handler 暂停时不调用 success/failure finalize；取消 WAITING_REVIEW 时任务 CANCELLED、invocation FAILED/USER_CANCELLED。

### 6. MySQL 保存业务任务和 checkpoint

通过 Alembic 为 `file_parse_task` 增加 `original_filename`，并新增 `risk_assessment_task`、`risk_assessment_document`、`risk_review_event`、`risk_graph_checkpoint`。RiskAssessmentDocument 保存 original_filename 快照、declared_document_type 和紧凑类型校验状态/warnings；完整 ParsedDocument 仍引用 file_parse snapshot，抽取结果保存在风险文档关联上。task 的 `result_snapshot` 保存可查询的当前审计结果或最终结果。图 state/checkpoint 只保存恢复所需 ID、受影响字段、checkpoint version 和下一节点，不复制完整 ParsedDocument、OCR 文本或复核展示快照。

MySQL checkpointer 通过 adapter 实现，领域图依赖抽象。Redis 只可用于 worker/锁，不作为唯一恢复源。

### 7. 文档事实融合和规则是纯后端逻辑

规范化器处理 ExtractedField 中的金额、重量、单位、日期、合同号和公司名称。resolver 使用字段值、sources 和 alternatives 形成跨文档事实；公式规则处理数量×单价、保证金/预付款比例、结算金额和日期时序。自动选择必须输出 rule code、input evidence 和版本。

字段按关键级别配置：critical 冲突必须人工；non-critical 可输出 warning。最终状态使用 `CHECKED`、`NEEDS_REVIEW`、`INCONSISTENT` 或等价稳定枚举，不等同审批结论。

### 8. 业务模式只保留审批样表原文

本阶段直接消费 ApprovalFormExtractor 的 `raw_business_mode_text`、status 和 sources，并作为普通审计字段进入任务结果与复核上下文。系统不定义 `BusinessModeCode`、mapping status、别名表或 enum version，也不从采购/销售合同特征推断业务模式。未来业务枚举确认后，通过 `fact_enrichers` 注册独立 mapper，并以新 change 增加版本化映射契约；现有图节点和原始证据无需改写。

### 9. API 以显式执行和恢复为主

```text
POST /api/v1/internal/risk-assistant/tasks
GET  /api/v1/internal/risk-assistant/tasks/{id}
POST /api/v1/internal/risk-assistant/tasks/{id}/execute
POST /api/v1/internal/risk-assistant/tasks/{id}/reviews
POST /api/v1/internal/risk-assistant/tasks/{id}/cancel
```

create 只创建 PENDING；execute 启动图；reviews 仅允许 WAITING_REVIEW；所有操作使用 Cookie subject、归属和部门权限。第三阶段前端只消费这些 API。

`GET /tasks/{id}` 同时承担普通结果查询和 WAITING_REVIEW 上下文查询，避免本阶段新增只服务展示的独立 endpoint。响应 schema 显式投影 task/document/check/review 数据，不暴露 checkpoint 原始 state。

## Risks / Trade-offs

- [TaskHandler 通用层被暂停语义污染] → 扩展点可选，合同审查回归覆盖，未启用 handler 行为不变。
- [MySQL checkpointer 实现复杂] → 先做恢复 spike；state 保持轻量并用专用表/adapter。
- [业务模式枚举延期导致后续迁移] → 始终保存审批样表原文和稳定证据，使用通用 `fact_enrichers` 扩展点接入后续 mapper。
- [完整复核上下文响应过大] → 仅返回审计字段目录内的结构化值、必要 quote/定位和规则摘要，不返回完整 OCR/ParsedDocument；原文按来源 ID 继续可追溯。
- [原始文件名包含路径或敏感业务信息] → 只持久化 basename、限制长度和扩展名一致性，不写对象 key；仍按任务归属权限控制查询。
- [文件名与正文冲突或正文无标题] → 文件名永不作为唯一分类依据；内容冲突标记 SUSPECTED，证据不足标记 UNVERIFIED，均不自动切换 extractor。
- [扫描件类型校验导致重复 OCR] → validator 必须消费同一次 provider OcrDocument，测试断言每份扫描件仍只调用一次 PaddleOCR 和一次 Qwen。
- [人工等待导致长期 invocation] → task 明确 WAITING_REVIEW，snapshot 标记等待，配置取消/超时策略。
- [规则过早固化] → 规则配置带版本，首期只实现样本可验证公式和业务已确认容差。

## Migration Plan

1. 为 file_parse_task 增加 nullable original_filename 列，更新所有新建调用方强制传值；存量行保持兼容但不能进入新风控任务。
2. 更新 extraction provider 临时 warning 协议和内容校验，保持 DocumentExtractionResult 契约不变。
3. 新增风险枚举/model/migration/repository，feature flag 默认关闭。
4. 扩展 TaskHandler suspend/resume 并跑合同审查回归。
5. 实现 graph/checkpointer、类型校验节点和文档事实规则。
6. 注册 RISK_ASSISTANT handler、API 和 internal seed。
7. 用 API 集成测试走通自动完成、类型冲突、暂停、恢复和取消。

回滚时关闭 risk assistant feature flag 和路由；保留新增表只读，不影响合同审查/external profile。

## Open Questions

- 首期审计字段目录、关键字段等级和展示顺序。
- WAITING_REVIEW 最长保留时间及代办权限。
- 是否允许缺少审批表/结算单时完成“部分核对”。
- 第三阶段 ERP 节点失败时应等待复核还是允许带 warning 完成。

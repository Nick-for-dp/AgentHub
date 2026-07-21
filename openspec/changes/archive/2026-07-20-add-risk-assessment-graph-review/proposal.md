## Why

在文档事实抽取契约稳定后，风控助手需要把多份文档事实组织为一个可审计任务，运行确定性核对，并在关键冲突时暂停等待人工再恢复。普通顺序 service 或 Dify 多分支难以可靠承载同一执行的 checkpoint、interrupt/resume 和调用审计。

本 change 是原 `add-risk-assistant-agent-mvp` 的第二阶段拆分，依赖 `add-risk-document-extraction-foundation` 已提供稳定的 DocumentExtractionResult/ExtractedField 契约，对应 `PLAN-internal.md` I7 的任务编排、规则核对和人工复核部分，引用 ADR-014、ADR-015、ADR-017、ADR-018。

## What Changes

- 新增 `RISK_ASSISTANT` 任务型 Agent、风控任务/文件关联/复核事件/checkpoint 数据模型和 internal API。
- **BREAKING（internal file-parse API）**：创建 `file_parse_task` 时必须同时提交原始文件名；系统将规范化后的 basename 持久化并贯穿解析、风险文档关联、结果和复核上下文，对象存储 key 仍保持随机化。
- 使用一张 LangGraph 图编排多文件抽取、字段规范化、跨文档事实解析、确定性核对和复核路由。
- 加强声明文档类型校验：调用方声明仍决定专用 extractor，原始文件名只作弱提示；普通文档使用 ParsedDocument 内容，扫描件复用同一次 PaddleOCR 版面文本进行标题/结构冲突检查，不要求“01X销售合同”等精确命名，也不自动切换 extractor。
- 将人工复核纳入同一图：关键冲突时 interrupt，任务进入 WAITING_REVIEW；人工提交后从同一 checkpoint 恢复并重跑受影响校验。
- WAITING_REVIEW 查询返回当前任务全部审计字段、状态、候选值、证据和核对结果；只有待复核项允许提交人工决定，其余信息作为只读上下文。
- 扩展 TaskHandler 通用模板的可选暂停/恢复钩子，同时保持合同审查既有执行路径不变。
- 建立金额、数量、比例、日期时序等确定性核对规则；第一阶段只提供 ExtractedField，最终跨文档事实和核对状态由后端生成。
- 业务模式本阶段只保留审批样表抽取的原文及证据，不做枚举或别名映射，也不因未映射触发人工复核；通过通用事实扩展点为后续映射能力预留接入位置。
- 提供 API 级复核与查询能力；本阶段通过 API 和自动化测试验收，不建设正式业务工作台。

Non-goals：

- 不更换或重新实现扫描 OCR、Qwen 字段选择和四类 extractor；只扩展原始文件名链路及现有 provider 的确定性类型校验 warning。
- 不接入 ERP，不做文档与 ERP 对账。
- 不定义业务模式枚举、别名表或映射版本；这些内容待业务侧确认后通过后续 change 接入。
- 不建立基于文件名的自动分类或硬编码命名规则，不支持因校验冲突自动改写调用方声明类型。
- 不建设正式多栏 Web 工作台和审计底稿 Excel 导出。
- MVP 不实现自由式 ReAct；复核使用确定性重试加人工 interrupt/resume。

## Capabilities

### New Capabilities

- `risk-assistant-task-execution`: 多文件风控任务、LangGraph 执行、状态持久化和 invocation 审计。
- `risk-assistant-human-review`: 完整审计信息复核视图、WAITING_REVIEW、人工决定审计、checkpoint 恢复和重新校验。

### Modified Capabilities

- `agent-task-handler-dispatch`: 注册 RISK_ASSISTANT handler，并增加不影响合同审查的可选暂停/恢复扩展点。
- `risk-document-parsing`: file_parse_task 创建、解析结果和查询响应持久化规范化后的原始文件名。
- `risk-document-fact-extraction`: 在不增加第二次 OCR/VLM 调用的前提下，以内容为主、文件名为弱提示校验 declared_document_type。

## Impact

- 新增 `backend/app/modules/risk_assessment/` 的 model/repository/service/rules/graph/task_handler、审计信息视图组装和 internal endpoints。
- 修改 `file_parse_task` model/migration/create/read schema、FileParseService 和既有 internal 调用方，使原始文件名不再在随机对象 key/临时文件链路中丢失。
- 修改 DocumentExtractionProvider 临时返回协议和类型校验逻辑，复用 Prepared OCR/ParsedDocument 文本产生稳定校验 warning，同时保持 DocumentExtractionResult 顶层字段不变。
- 增加 LangGraph/LangChain internal optional 依赖和 MySQL checkpoint adapter。
- 新增 Alembic migration、Agent/Operation/TaskStatus 枚举和 internal seed。
- 修改通用 TaskHandler pipeline 的可选暂停/恢复协议，并补合同审查回归测试。
- 不修改 external profile、ERP integration 或正式前端工作台。

## Why

`PLAN-internal.md` I3/I7 要求风控助手读取采购合同、销售合同、审批表和结算单。作为一期项目，优先目标不是建立通用文档 AI 平台，而是用最少的数据对象和步骤，稳定得到后续风控核对所需的字段和证据。

本 change 是三阶段方案的第一阶段，只交付“单文件 → 字段结果”的最小能力，遵守 ADR-018。DOCX 默认是已接受修订的最终版；OCR/VLM 采用“PaddleOCR-VL-1.6 负责文档解析和位置、Qwen3.7-Plus 负责语义理解和字段选择”的候选生产路线，并通过代表样本 spike 确认参数、准确率、成本和数据边界，不建设通用感知编排框架。

## What Changes

- 保持现有 `ParsedDocumentV1` 顶层结构不变，补齐扫描 PDF 识别、PNG/JPG 接入和普通 DOCX 合并单元格处理。
- 上传或创建风险文件关联时，由用户明确声明四种文档类型之一；一期不开发自动文档分类器。
- 只定义一个 `DocumentExtractionProvider` 抽象，并实现一个组合型候选 adapter：扫描 PDF/图片先通过 PaddleOCR-VL-1.6 API 获得按页文字、版面和坐标，再由 Qwen3.7-Plus API 根据专用 schema 选择字段；普通 DOCX 直接使用既有解析文本进入 Qwen，跳过 OCR。
- PaddleOCR 是扫描件文字、页码、稳定 source ID 和可选 bbox 的唯一位置权威；Qwen 只返回字段值、证据 quote 和 source IDs，不生成或裁决 bbox。无法映射回 PaddleOCR 来源的结果统一进入 `UNCERTAIN`。
- 为采购合同、销售合同、审批表和结算单保留四个独立 extractor/schema，避免单一超大 Prompt。
- 只保留三个核心数据对象：
  - `ParsedDocumentV1`：现有文件解析结果；
  - `ExtractedField`：一个字段的值、状态和内嵌来源；
  - `DocumentExtractionResult`：一份文档的字段列表、warnings 和版本。
- 字段状态只使用 `FOUND / MISSING / UNCERTAIN`。冲突、低置信度和证据不足统一进入 `UNCERTAIN`，留给第二阶段规则或人工复核处理。

### 最小数据流

```text
FileParseTask(source_uri + ParsedDocumentV1)
  → 专用 DocumentExtractor（由 declared_document_type 直接选择）
  → DocumentExtractionResult(fields[])
```

OCR/VLM 调用、文本/图像路由、provider 原始响应、字段归一化和证据检查均为 extractor 内部实现细节，不建立独立节点和持久化对象。

组合 provider 的内部链路为：

```text
扫描 PDF/图片
  → PaddleOCR-VL-1.6 multipart job + 有界轮询
  → 带 Pxxx-Bxxx 稳定锚点的 OCR/版面结果
  → Qwen3.7-Plus 单次 ocr_text JSON 字段选择
  → source ID/quote 回映 PaddleOCR 页码与 bbox

普通 DOCX
  → ParsedDocumentV1 文本
  → Qwen3.7-Plus 单次 JSON 字段选择
  → block/quote 来源校验
```

明确删除以下一期设计：`DocumentRouteDecision`、`PagePerceptionRequest/Result`、`DocumentClassificationResult`、`ExtractionRequest`、`ProviderExtractionResult`、`FactCandidate`、`DocumentFact`、`DocumentValidationSignal`。

Non-goals：

- 不支持带未接受修订的 DOCX。
- 不自动判断文档类型；声明错误时返回 warning/UNCERTAIN，不建设分类模型。
- 不建设 OCR/VLM provider registry、通用 benchmark 平台或多策略动态路由。
- 不让 Qwen 坐标成为来源依据，不因 OCR/Qwen 不一致启动 ReAct 或无限自复核循环。
- 不做单文档公式校验、跨文档核对、业务模式枚举、LangGraph、人工复核、ERP、工作台或 Excel 导出。

## Capabilities

### New Capabilities

- `risk-document-parsing`: 扫描 PDF/图片接入、普通 DOCX 和合并表格的最小文件解析能力。
- `risk-document-fact-extraction`: 按声明文档类型选择专用 extractor，并输出极简字段结果契约。

### Modified Capabilities

## Impact

- 修改 `backend/app/integrations/file_reader/` 和 `modules/file_parse/`，但保持 `ParsedDocumentV1` 顶层兼容。
- 新增 `backend/app/modules/risk_assessment/extraction/` 的极简 schema、provider port、四类 extractor 和 service；不新增数据库表。
- 新增 PaddleOCR/Qwen 独立配置、显式云端数据出网开关和一个组合 provider adapter；使用现有异步 `httpx`，不增加同步 `requests` 依赖。provider 配置不依赖全局 deployment profile，只有经过风险任务 handler 的 Agent visibility、调用主体和权限校验后才能调用；任意 profile 导入应用时均不主动初始化 provider。
- PaddleOCR 接收 multipart 原文件；Qwen 一期只接收带稳定 source ID 的 OCR/ParsedDocument 文本，不接收页面图片，最终页码/bbox 只从 PaddleOCR 来源映射获得。

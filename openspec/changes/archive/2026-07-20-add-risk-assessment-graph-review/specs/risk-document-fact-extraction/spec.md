## MODIFIED Requirements

### Requirement: 文档类型必须由调用方声明

调用方 MUST 为每份文件声明 PURCHASE_CONTRACT、SALES_CONTRACT、APPROVAL_FORM 或 SETTLEMENT_STATEMENT。系统 SHALL 直接按声明类型选择 extractor，不运行自动文档分类模型，也 MUST NOT 要求原始文件名精确匹配“01X销售合同”等固定编号或名称。

系统 SHALL 使用版本化确定性规则校验 declared_document_type：原始文件名只作为弱提示，ParsedDocument/OCR 内容中的标题和结构标记是主要依据。普通文本文件 MUST 使用 ParsedDocumentV1 blocks；扫描 PDF/图片 MUST 复用本次字段抽取已经产生的 PaddleOCR OcrDocument，MUST NOT 为类型校验增加第二次 PaddleOCR、Qwen 或其他模型调用。内容与声明明显冲突时结果 MUST 包含 DOCUMENT_TYPE_SUSPECTED warning，相关非空字段标记 UNCERTAIN，系统不得自动切换 extractor；没有足够内容标记时 SHALL 输出 DOCUMENT_TYPE_UNVERIFIED warning。

#### Scenario: 用户声明采购合同
- **WHEN** 文件关联的 declared_document_type 为 PURCHASE_CONTRACT
- **THEN** 系统只运行 PurchaseContractExtractor

#### Scenario: 声明类型疑似错误
- **WHEN** 专用 extractor 在 ParsedDocument 或 PaddleOCR 内容中发现标题/结构与声明类型明显冲突
- **THEN** 结果包含 DOCUMENT_TYPE_SUSPECTED warning，相关字段标记 UNCERTAIN，系统不自动切换 extractor

#### Scenario: 非标准销售合同文件名
- **WHEN** original_filename 为 `客户供货协议.pdf`、declared_document_type 为 SALES_CONTRACT 且内容符合销售合同标记
- **THEN** 系统按 SALES_CONTRACT 抽取且不因文件名缺少“01X销售合同”而报错

#### Scenario: 扫描件复用 OCR 做类型校验
- **WHEN** 扫描 PDF 需要 PaddleOCR 才能看到合同标题
- **THEN** 系统使用同一次 PaddleOCR 结果完成类型校验和 Qwen 字段选择，每个文件仍最多调用一次 PaddleOCR 和一次 Qwen

#### Scenario: 内容无法验证类型
- **WHEN** 文件名和 ParsedDocument/OCR 内容均没有足够的文档类型标记
- **THEN** 系统保留调用方声明、不切换 extractor，并输出 DOCUMENT_TYPE_UNVERIFIED warning

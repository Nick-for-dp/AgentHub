## ADDED Requirements

### Requirement: ParsedDocument 顶层契约必须保持不变

系统 SHALL 继续输出 `metadata/blocks/sections/warnings` 形式的 ParsedDocumentV1。第一阶段 MUST NOT 为页面路由、OCR 结果或模型结果增加新的顶层对象。

#### Scenario: 合同审查读取增强后的解析结果
- **WHEN** 文件解析能力增加扫描 warning 或图片 reader
- **THEN** 既有合同审查仍按 ParsedDocumentV1 blocks 构造全文输入

### Requirement: 扫描 PDF 不得伪装为有效文本 PDF

PdfReader SHALL 检测空文本、扫描水印或明显低质量文本，并输出稳定 warning。系统 MUST NOT 把水印或空文本当作有效合同正文；原文件仍通过 file_parse_task.source_uri 保留给后续 extractor 使用。

#### Scenario: PDF 只有扫描水印
- **WHEN** 页面原生文本仅包含“扫描全能王 创建”
- **THEN** ParsedDocument 输出 SCANNED_TEXT_UNAVAILABLE warning，不生成虚假的有效正文

### Requirement: 图片必须进入统一文件解析任务

internal file parse SHALL 支持 PNG/JPG。ImageReader SHALL 输出基础 metadata、空或最小 blocks 以及 IMAGE_REQUIRES_EXTRACTION warning；external profile MUST NOT 因此加载 internal 模型依赖。

#### Scenario: 创建 JPG 结算单解析任务
- **WHEN** internal 用户提交 JPG source_uri
- **THEN** file_parse_task 成功保存 ParsedDocumentV1，并明确提示后续 extractor 需要读取原图

### Requirement: DOCX 首期只保证非修订最终版

DocxReader SHALL 读取普通非修订 DOCX 的段落、表格、样式和文档顺序。本能力 MUST NOT 声称解释未接受修订或修订历史。

#### Scenario: 已接受修订的审批表
- **WHEN** 用户上传已接受全部修订并另存的 DOCX
- **THEN** 系统按普通段落和表格读取，不需要 revision parser

### Requirement: 合并单元格不得重复语义内容

DocxReader MUST 将同一合并单元格的文本输出一次，并在表格 metadata 中保留足够的行列信息。

#### Scenario: 业务模式简介横跨多列
- **WHEN** 一个表格单元格横跨多个物理列
- **THEN** ParsedDocument 只保留一份业务模式正文

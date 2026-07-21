# risk-document-parsing

为风险文档提供兼容既有 ParsedDocumentV1 的最小解析增强，覆盖扫描 PDF、图片和普通非修订 DOCX。

## Purpose

确保扫描件不会被误当作可靠文本，让图片和普通非修订 DOCX 进入统一文件解析链路，消除合并单元格的重复语义内容，并持续保持既有合同审查对 ParsedDocumentV1 顶层契约的兼容性。

## Requirements

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

### Requirement: file parse 必须持久化原始文件名

internal file parse 创建请求 SHALL 同时提供 source_uri 和 original_filename。系统 MUST 将 original_filename 规范化为 basename 后持久化到 file_parse_task、查询响应和 ParsedDocumentV1.metadata.filename；对象存储 key MUST 继续使用随机名称，不得直接包含原始文件名。新建风险任务 MUST NOT 使用随机对象 key 或解析临时文件名作为来源文件名称。

#### Scenario: 上传后创建解析任务
- **WHEN** 上传准备响应返回 original_filename=`5.01X销售合同.pdf` 和随机化 storage_uri，调用方创建 file_parse_task
- **THEN** file_parse_task 和 ParsedDocumentV1.metadata.filename 保存 `5.01X销售合同.pdf`，source_uri 仍指向随机对象 key

#### Scenario: 文件名包含客户端路径
- **WHEN** 调用方提交 original_filename=`C:\\Users\\user\\客户销售合同.pdf`
- **THEN** 系统只保存 basename `客户销售合同.pdf`，不保存客户端目录

#### Scenario: 文件名扩展名与对象类型冲突
- **WHEN** original_filename 扩展名为 `.docx` 而 source_uri 对象扩展名为 `.pdf`
- **THEN** 系统拒绝创建解析任务，不生成不一致的来源元数据

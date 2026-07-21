## ADDED Requirements

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

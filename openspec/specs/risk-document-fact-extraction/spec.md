# risk-document-fact-extraction

按调用方声明的供应链文档类型，从单份文档中抽取可追溯、可版本化的极简字段结果。

## Purpose

为风控助手提供采购合同、销售合同、审批表和结算单的单文档字段抽取能力，同时约束 OCR/VLM 数据边界、证据回映和结果契约。

## Requirements

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

### Requirement: 系统只使用一个文档抽取 provider 端口

系统 SHALL 通过 DocumentExtractionProvider 隔离具体 OCR/VLM/文本模型。候选生产实现 SHALL 在内部组合 PaddleOCR-VL-1.6 API 和 Qwen3.7-Plus API：PaddleOCR 负责扫描 PDF/图片的文档解析和位置，Qwen 负责语义理解和字段选择。生产 adapter MUST 在代表样本轻量 spike 和 ADR 完成后启用；领域层 MUST NOT 建立独立页面感知、路由或 provider registry。

#### Scenario: 扫描采购合同抽取
- **WHEN** PurchaseContractExtractor 抽取扫描 PDF
- **THEN** 领域层只调用一次 DocumentExtractionProvider，provider 内部先调用 PaddleOCR，再调用一次 Qwen，不暴露中间领域对象

#### Scenario: 普通 DOCX 审批表抽取
- **WHEN** ApprovalFormExtractor 抽取有可靠文本层的 DOCX
- **THEN** provider 跳过 PaddleOCR，直接使用 ParsedDocumentV1 文本和 block ID 调用一次 Qwen

#### Scenario: ADR 尚未完成
- **WHEN** 技术 spike、数据出网审批或 ADR 尚未完成
- **THEN** 系统只运行 fake provider contract tests，production provider factory 必须 fail closed

### Requirement: PaddleOCR 必须是扫描件来源位置的唯一权威

系统 MUST 为 PaddleOCR 按页版面结果生成稳定 source ID，并保留 page、quote 和可选 bbox。Qwen MUST 只返回字段值、quote 和 source IDs；系统 MUST NOT 把 Qwen 自报坐标作为 ExtractedField 来源。一期 Qwen production 调用 MUST 使用 `ocr_text`，不得上传页面图片。

#### Scenario: Qwen 返回可映射来源
- **WHEN** Qwen 返回 source ID `P001-B004` 且 quote 能匹配对应 PaddleOCR block
- **THEN** 系统使用该 PaddleOCR block 的 page、quote 和 bbox 组装 FOUND 来源

#### Scenario: Qwen 返回不存在的 source ID
- **WHEN** Qwen 返回的 source ID 不存在，或 quote 与数值 raw value 均无法在对应 OCR block 中归一化定位
- **THEN** 系统不得猜测 bbox，字段标记为 UNCERTAIN

#### Scenario: OCR 与 Qwen 数值冲突
- **WHEN** Qwen 选择的金额、数量或日期无法通过归一化匹配回 OCR 证据
- **THEN** 字段标记为 UNCERTAIN，可保存简单 alternatives，不启动 ReAct 或额外模型循环

### Requirement: 云端 OCR/VLM 调用必须有明确数据边界

PaddleOCR/Qwen 组合 provider MUST 仅在显式 cloud-egress 开关启用且风险任务 handler 已校验 Agent visibility、调用主体和权限后调用。provider 配置和 factory MUST NOT 使用全局 deployment profile 代替资源授权；应用在任意 profile 导入时 MUST NOT 主动初始化 provider。PaddleOCR MUST 使用 multipart 上传原文件；系统 MUST NOT 为云端 provider 暴露可公开访问的 MinIO 原文件 URL。Qwen 一期只能接收 OCR/ParsedDocument 文本。密钥、Base64、provider 原始响应、签名结果 URL 和模型推理文本 MUST NOT 进入 DocumentExtractionResult、日志或 repr。

#### Scenario: 未批准数据出网
- **WHEN** cloud-egress 开关未启用
- **THEN** production provider factory 明确失败，不上传任何合同或页面图片

#### Scenario: 同一部署同时包含 internal 和 external Agent
- **WHEN** 应用实例中同时存在不同 visibility 的 Agent
- **THEN** deployment profile 不决定 provider 调用权限，只有通过风险任务 handler 授权的内部 Agent 调用可以进入 provider

#### Scenario: PaddleOCR 任务持续未完成
- **WHEN** PaddleOCR job 超过轮询总时长或进入未知状态
- **THEN** adapter 停止轮询并返回受控 provider 错误，不无限等待

#### Scenario: PaddleOCR 返回结果 URL
- **WHEN** provider 返回 JSONL 或图片下载 URL
- **THEN** adapter 只允许 HTTPS 和配置允许的主机，下载后不持久化签名 URL

### Requirement: 四类文档必须使用独立 extractor

四类文档 MUST 使用独立 output schema、prompt 和字段白名单，MUST NOT 使用包含所有字段的单一超大 Prompt。每份文档的 extractor 最多调用一次 provider；组合 provider 对每份文档最多调用一次 Qwen。

#### Scenario: 销售合同抽取
- **WHEN** declared_document_type 为 SALES_CONTRACT
- **THEN** 系统只请求下游客户、合同号、日期、地点、数量、单价和金额等销售字段

### Requirement: 字段结果必须使用极简状态

每个 ExtractedField MUST 包含 field_code、raw_value、normalized_value、unit、status、sources 和可选 alternatives。status 只允许 FOUND、MISSING、UNCERTAIN；FOUND MUST 至少有一条可定位到 block、页码或原文 quote 的来源。

#### Scenario: 找到采购含税单价
- **WHEN** 系统抽取到 5350 元/吨并能定位原文
- **THEN** 字段为 FOUND，保存 raw/normalized value、CNY/TON 和来源

#### Scenario: 两个金额无法判断
- **WHEN** 同一文档出现两个有来源但无法消解的金额
- **THEN** 字段为 UNCERTAIN，并把两个值放入 alternatives

#### Scenario: 文档没有浮动费
- **WHEN** 文档中没有浮动费证据
- **THEN** 字段为 MISSING，不计算或推测默认值

### Requirement: 单文档输出必须保持最小且版本化

DocumentExtractionResult MUST 只包含 document_type、fields、warnings、parser_version、extractor_version 和 provider_version。系统 MUST NOT 在一期结果中保存 DocumentRouteDecision、PagePerceptionResult、ProviderExtractionResult、FactCandidate、DocumentFact 或 DocumentValidationSignal。

#### Scenario: 抽取器升级
- **WHEN** PurchaseContractExtractor 从 v1 升级到 v2
- **THEN** 新结果记录 v2，历史结果仍可区分旧版本

### Requirement: 首期字段必须按来源抽取

系统 SHALL 抽取业务总览所需的原始文档字段：业务模式原文、上游供应商、下游客户、货物名称、采购/销售合同号及签订日、交货地点、采购/销售含税单价、合同数量、采购/销售含税金额、大客户优惠、保证金比例/金额、浮动费和占用天数。没有来源时 MUST 返回 MISSING 或 UNCERTAIN。

`raw_business_mode_text` MUST 只读取审批样表“业务性质”栏的已勾选项和对应自由填写内容，MUST NOT 读取“业务模式简介”长文本。该字段可按参考底稿生成可读原文表达，但不得定义正式业务模式枚举、别名版本或从其它合同推断。

#### Scenario: 审批表从业务性质提取业务模式
- **WHEN** “业务性质”栏勾选“预付款”和“其他（联销等）”并填写“联销”，相邻行存在较长“业务模式简介”
- **THEN** ApprovalFormExtractor 返回“联销（预付款+联合销售）”及“业务性质”表格行来源，不返回“业务模式简介”正文

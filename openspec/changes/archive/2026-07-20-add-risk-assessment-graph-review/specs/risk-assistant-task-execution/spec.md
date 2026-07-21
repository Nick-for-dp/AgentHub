## ADDED Requirements

### Requirement: internal 用户可创建多文件风控任务

internal 用户 SHALL 创建 PENDING 风控任务并关联属于其可见范围、状态为 SUCCEEDED 且已持久化 original_filename 的多个 file_parse_task，同时为每份文件声明文档类型。创建 MUST 从 file_parse_task 快照保存原始文件名、用户、组织、业务编号、声明类型和文件顺序，且 MUST NOT 接受请求重新指定来源文件名、执行文档抽取、启动 LangGraph 或创建成功 invocation。

#### Scenario: 创建采购销售文件包
- **WHEN** 用户提交两个有效 file_parse_task 并分别声明采购合同和销售合同
- **THEN** 系统创建一个 PENDING 任务和两条带 original_filename 快照的文件关联，不执行图

#### Scenario: 越权文件被拒绝
- **WHEN** 用户关联不属于自己的解析结果
- **THEN** 系统拒绝创建且不泄露文件内容

#### Scenario: 原始文件名缺失
- **WHEN** 用户引用一个存量但 original_filename 为空的 file_parse_task
- **THEN** 系统拒绝创建风控任务并提示重新上传解析，不以随机对象 key 或临时文件名代替

### Requirement: RISK_ASSISTANT handler 必须运行单一 LangGraph

只有 PENDING 任务 MUST 可 execute。系统 SHALL 经 TaskHandlerRegistry 选择 RISK_ASSISTANT handler，创建 invocation，并运行文档抽取、字段规范化、跨文档事实解析、确定性规则和复核路由图。endpoint MUST NOT 包含图节点或规则实现。

#### Scenario: 合法任务执行
- **WHEN** 当前主体拥有 PENDING 任务且 Agent type 为 RISK_ASSISTANT
- **THEN** 任务进入 RUNNING，创建一条 invocation 并启动图

#### Scenario: 重复执行被拒绝
- **WHEN** 对 RUNNING/WAITING_REVIEW/终态任务再次普通 execute
- **THEN** 返回冲突，不创建第二条 invocation

### Requirement: 文档核对必须由确定性规则生成

系统 SHALL 在后端对金额、数量、比例和日期运行版本化规则。第一阶段 ExtractedField 的 provider confidence 不得作为唯一自动接受依据。每次自动选择或差异 MUST 保存 rule code、输入字段/alternatives、来源和版本。

#### Scenario: 公式裁决采购单价
- **WHEN** 单价字段为 UNCERTAIN 且 alternatives 为 5350/5850，数量 2000，合同金额 10700000
- **THEN** 公式规则支持 5350、保留 5850 和裁决证据

### Requirement: 风控图必须处理声明类型校验结果

系统 SHALL 在每份文档抽取后读取内容级类型校验 warning，并把 original_filename、declared_document_type 和 validation status 写入 RiskAssessmentDocument 及任务结果。`DOCUMENT_TYPE_SUSPECTED` MUST 形成关键复核信号；`DOCUMENT_TYPE_UNVERIFIED` MUST 作为 warning 展示。系统 MUST NOT 根据文件名或校验结果自动切换 extractor。

#### Scenario: 扫描采购合同被声明为销售合同
- **WHEN** PaddleOCR 内容明确包含采购合同冲突标记，而 declared_document_type 为 SALES_CONTRACT
- **THEN** 风控图保存 DOCUMENT_TYPE_SUSPECTED、保持原声明和来源文件名，并进入 WAITING_REVIEW

#### Scenario: 非标准文件名但内容一致
- **WHEN** 文件名为“客户供货协议.pdf”、declared_document_type 为 SALES_CONTRACT 且正文内容符合销售合同标记
- **THEN** 系统继续按销售合同处理，不要求文件名包含“01X销售合同”或固定编号

### Requirement: 风控结果必须版本化并可追溯

成功结果 MUST 保存 schema、parser/extractor、rule 和 graph 版本，以及 audit items、document facts、checks、warnings 和总体核对状态。后续版本不得改写历史结果。

#### Scenario: 规则版本升级
- **WHEN** 新规则发布
- **THEN** 历史任务仍显示原版本，显式 rerun 才产生新结果

### Requirement: 业务模式本阶段必须保留审批样表原文

系统 SHALL 将 ApprovalFormExtractor 输出的 `raw_business_mode_text`、status 和 sources 作为普通审计字段保存在当前及最终结果中。系统 MUST NOT 在本阶段定义业务模式枚举、别名映射或 mapping status，也 MUST NOT 从采购合同或销售合同特征推断业务模式。事实处理流程 SHALL 保留可注册的 enrichment 扩展点，供后续 change 接入正式映射能力。

#### Scenario: 审批样表包含业务模式描述
- **WHEN** 审批样表抽取结果包含“联销（预付款+联合销售）”或更长的业务模式原文
- **THEN** 风控结果原样保留该文本及来源证据，不生成业务模式代码

#### Scenario: 审批样表缺少业务模式
- **WHEN** ApprovalFormExtractor 返回 raw_business_mode_text=MISSING
- **THEN** 风控结果保留 MISSING 状态，且不尝试从其他合同推断

### Requirement: 任务和 invocation 必须一致收口

自动成功时 task/invocation MUST SUCCEEDED；异常时 MUST FAILED；取消 MUST 可识别。WAITING_REVIEW 时 invocation MUST 保持未完成并记录 execution_state，而不是错误成功。

#### Scenario: 图等待人工
- **WHEN** 图 interrupt
- **THEN** task 为 WAITING_REVIEW，invocation 未完成且引用同一 graph thread

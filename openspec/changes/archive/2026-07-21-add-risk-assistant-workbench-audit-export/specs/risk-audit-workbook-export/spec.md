## ADDED Requirements

### Requirement: 导出必须只包含业务总览 sheet

系统 SHALL 为有权用户生成 `.xlsx` 审计底稿，且 workbook MUST 只包含一个可见、名称为“业务总览”的 sheet。系统 MUST NOT 生成隐藏 metadata，也不得复制“单据清单、数量核对、金额核对、资金流向、差异汇总、数据溯源”等其它 sheet 或样例历史业务数据。

#### Scenario: 导出已完成任务
- **WHEN** 用户导出一个 SUCCEEDED 风控任务
- **THEN** 下载的 workbook 仅有“业务总览”一个 sheet

### Requirement: 业务总览布局必须匹配参考底稿第一张表

“业务总览” SHALL 使用 `A1:C22`：标题、业务编号和编制日期、章节标题、项目/内容/来源文件表头，以及 17 个固定业务项目。系统 SHALL 使用版本化、确定性样式生成微软雅黑、深蓝表头、白字、边框、对齐、列宽和换行，不得依赖带业务数据的样例 workbook 作为运行时模板。

#### Scenario: 检查导出布局
- **WHEN** 测试读取生成的 workbook
- **THEN** `A1:C22` 的标题、表头、17 个项目顺序、合并区域和关键样式与模板版本一致

### Requirement: Web 与 Excel 必须复用同一业务总览投影

导出 service SHALL 使用与工作台相同的 `BusinessOverviewProjector` 生成项目内容、状态和来源文件，不得在 Excel writer 中维护第二套字段选择或组合规则。投影 MUST 不修改 canonical result。

#### Scenario: 人工复核后导出
- **WHEN** 某字段已经通过 HUMAN_REVIEW 得到最终值
- **THEN** 工作台业务总览与 Excel 内容显示相同最终值，Excel 来源文件追加人工复核标识

### Requirement: 业务总览必须映射固定 17 项

系统 SHALL 输出业务模式、上下游主体、货物名称、采购/销售合同号及签订日、交货地点、采购/销售含税单价、合同约定数量、采购/销售含税金额、大客户优惠、保证金比例和浮动费共 17 项。业务模式 MUST 使用审批样表“业务性质”栏已勾选项形成的可读原文表达；大客户优惠 MUST 按 CNY 金额展示。

#### Scenario: 输出真实样例字段
- **WHEN** canonical result 包含采购单价 5350、销售单价 5500 和大客户优惠 31074.58
- **THEN** 对应行分别显示元/吨、元/吨和元金额，不把大客户优惠显示为元/吨

### Requirement: 合同数量必须只展示约定事实

“合同约定数量” SHALL 读取采购合同数量和销售合同数量，但 MUST NOT 将两者比较结果解释为风险、匹配或不匹配。两值相同时可合并展示；两值不同时必须中性展示各自约定值和来源，不能任选一个或触发推断。

#### Scenario: 两份合同数量不同
- **WHEN** 采购合同约定 2000 吨而销售合同约定 1980 吨
- **THEN** 内容显示“采购约定：2000 吨；销售约定：1980 吨”，来源列保留两份原始文件名且不输出风险结论

### Requirement: 组合字段必须区分原文值和已确认公式派生值

保证金行 SHALL 组合明确识别的比例和金额；当保证金金额未明示、采购合同含税金额和保证金比例均可用时，系统 SHALL 按“采购合同含税金额 × 保证金比例 ÷ 100”确定性生成保证金金额，并保留输入来源和规则标识。浮动费行 SHALL 组合明确识别的费用和占用天数，仍不得推算缺失值。其它缺少组合项的情况 MUST 标记未识别或部分信息。MISSING、PARTIAL、NEEDS_REVIEW 和人工确认缺失 MUST 使用稳定文本表示。

#### Scenario: 保证金金额按已确认公式生成
- **WHEN** 采购合同含税金额为 10,700,000 元、保证金比例为 15%，且合同未明示保证金金额
- **THEN** 系统生成 1,605,000 元保证金金额，Excel 显示“15%（1,605,000元）”，来源关联采购含税金额和保证金比例，不伪装为合同明示金额

### Requirement: 来源文件必须使用持久化原始名称

来源文件列 SHALL 从 canonical sources 和任务文档快照提取原始文件名并去重。系统 MUST NOT 使用固定“01X销售合同”等别名替代用户上传名称；人工复核后的值 SHALL 在真实来源名称后追加人工复核标识。

#### Scenario: 非标准文件名来源
- **WHEN** 下游客户来自原始文件名“客户供货协议.pdf”
- **THEN** Excel 来源文件显示“客户供货协议.pdf”，不硬编码“01X销售合同”

### Requirement: 导出必须校验任务状态和归属

只有任务拥有者 SHALL 能导出 SUCCEEDED task。PENDING、RUNNING、WAITING_REVIEW、FAILED、CANCELLED 或越权请求 MUST 被拒绝；导出不得触发 Agent runtime、重新 OCR、重新执行 LangGraph 或修改任务结果。

#### Scenario: 待复核任务导出
- **WHEN** 用户请求导出 WAITING_REVIEW 任务
- **THEN** 系统返回业务冲突且不生成文件

#### Scenario: 越权导出
- **WHEN** 用户请求导出不属于自己的任务
- **THEN** 系统拒绝且不泄露业务编号、字段或来源文件

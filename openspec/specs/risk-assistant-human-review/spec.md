# risk-assistant-human-review

定义风控任务的完整审计复核上下文、人工决定审计和同一 LangGraph thread 的 checkpoint 恢复。

## Purpose

让关键字段冲突、跨文档候选和声明类型疑点可以安全暂停并交由有权用户复核，同时完整保留审计上下文、人工决定、证据来源、乐观锁版本以及跨请求恢复链路，确保任务与 invocation 始终可追溯且一致收口。

## Requirements

### Requirement: 未解决关键项必须暂停同一图

关键字段的 ExtractedField 为 UNCERTAIN、跨文档规则仍保留多个 alternatives，或任一来源文档为 DOCUMENT_TYPE_SUSPECTED 时，LangGraph MUST interrupt，任务进入 WAITING_REVIEW，并保存 checkpoint、review items 和 invocation 引用。业务模式原文未枚举化 MUST NOT 单独触发人工复核。

#### Scenario: 关键数量存在两个候选
- **WHEN** 第一阶段数量字段的 alternatives 为两个值，且跨文档规则无法排除任一值
- **THEN** 图暂停并展示两个候选、证据和冲突原因

#### Scenario: 业务模式只有原文
- **WHEN** 审批样表已提取业务模式原文但系统尚未配置枚举映射
- **THEN** 系统保留原文和证据，且不因为缺少枚举代码进入 WAITING_REVIEW

#### Scenario: 来源文档类型冲突
- **WHEN** 销售合同关联文件的内容校验返回 DOCUMENT_TYPE_SUSPECTED
- **THEN** 图创建 DOCUMENT_TYPE review item，展示 original_filename、declared type 和冲突 warning 后暂停

### Requirement: 人工复核必须展示完整审计信息

WAITING_REVIEW 任务的查询结果 SHALL 返回 `review_context`，其中 MUST 按审计字段目录展示当前任务全部审计字段，包括 FOUND、MISSING 和 UNCERTAIN 项的原始值、规范化值、单位、来源文件原始名称、declared_document_type、文档类型校验状态/warnings、证据位置、alternatives、关联核对结果和 warning。系统 MUST 标记每项是否为当前 review target；非 review target MUST 只读。

#### Scenario: 关键货物名称等待复核
- **WHEN** 货物名称为 UNCERTAIN 并触发 WAITING_REVIEW
- **THEN** review_context 同时展示货物名称候选及其证据，以及上下游主体、金额、数量、比例、日期和业务模式原文等其余审计信息

#### Scenario: 缺失字段仍展示
- **WHEN** 某个已配置审计字段没有可识别值
- **THEN** review_context 中仍包含该字段并标记 MISSING，而不是从复核上下文省略

#### Scenario: 来源文件类型疑似错误
- **WHEN** 某份原始文件名为“采购资料.pdf”的文件被声明为 SALES_CONTRACT 且内容校验为 SUSPECTED
- **THEN** review_context 展示原始文件名、声明类型和 DOCUMENT_TYPE_SUSPECTED warning，人工无需依赖对象存储 UUID 判断来源文件

### Requirement: 人工决定必须审计

review event MUST 保存 target_kind、target_code、原值/alternatives、新值或确认动作、原因、操作人、sources、checkpoint version 和时间。人工来源 MUST 标记 HUMAN_REVIEW。DOCUMENT_TYPE review 只允许人工确认当前声明；若人工认为声明错误，MVP SHALL 通过取消并以正确类型重建任务处理，不得在同一 thread 自动切换 extractor。

#### Scenario: 人工选择单价
- **WHEN** 有权用户选择 5350 并填写公式核对原因
- **THEN** 系统保存 review event，原候选仍可追溯

#### Scenario: 人工确认非标准命名的销售合同
- **WHEN** 文档类型复核项展示 original_filename=`客户供货协议.pdf` 且人工确认 declared type=SALES_CONTRACT
- **THEN** 系统保存 DOCUMENT_TYPE 确认事件并恢复规则处理，不重复 OCR 或字段抽取

### Requirement: 恢复必须复用 thread 和 invocation

提交合法 review 后，系统 SHALL 从原 checkpoint 恢复同一 graph thread，只重跑受影响校验，并复用原 invocation。并发或重复 review MUST 通过 checkpoint version 拒绝。

#### Scenario: 跨请求恢复
- **WHEN** WAITING_REVIEW 任务收到合法 review
- **THEN** 任务回到 RUNNING，从 apply_human_review 继续且不重复 OCR/抽取

#### Scenario: 重复提交
- **WHEN** 两个请求使用相同旧 checkpoint version 提交
- **THEN** 只有一个成功，另一个返回冲突

### Requirement: 非等待任务不得接受人工复核

只有 WAITING_REVIEW、主体有权限、字段属于当前未解决 review items 且 checkpoint version 有效时 SHALL 接受 review。缺少原因、越权、修改只读上下文项或终态任务 MUST 拒绝。

#### Scenario: 缺少原因
- **WHEN** 用户修改值但不填写原因
- **THEN** 请求被拒绝，图状态不变

#### Scenario: 修改只读上下文项
- **WHEN** 用户尝试提交一个未被标记为 review target 的已确认字段
- **THEN** 请求被拒绝，原审计结果和 checkpoint 均保持不变

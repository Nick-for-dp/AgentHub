## ADDED Requirements

### Requirement: internal 用户可分页查询自己的风控任务

internal Cookie 用户 SHALL 按页查询其拥有的风控任务摘要，并可按状态筛选。列表 MUST 只返回任务 ID、业务编号、状态、当前节点、文件数量、时间和错误摘要等轻量信息，不返回 result、review_context、review events 或来源正文。

#### Scenario: 查询最近任务
- **WHEN** 用户请求第一页、每页 20 条风控任务
- **THEN** 系统按创建时间倒序返回该用户拥有的任务摘要和分页信息

#### Scenario: 列表权限隔离
- **WHEN** 同部门另一用户创建了风控任务
- **THEN** 当前用户的列表不返回该任务，除非后续权限 change 明确增加代办范围

## MODIFIED Requirements

### Requirement: 业务模式本阶段必须来自审批样表业务性质栏

系统 SHALL 将 ApprovalFormExtractor 从审批样表“业务性质”栏已勾选项得到的 `raw_business_mode_text`、status 和 sources 作为普通审计字段保存在当前及最终结果中。系统 MUST NOT 使用“业务模式简介”长文本代替该字段，MUST NOT 在本阶段定义业务模式枚举、别名映射或 mapping status，也 MUST NOT 从采购合同或销售合同特征推断业务模式。后续 ERP 或业务模式能力 SHALL 通过独立 change 演进 LangGraph；系统不要求当前演示图预建通用 enrichment 插件注册框架。

#### Scenario: 业务性质勾选预付款和联销
- **WHEN** 审批样表“业务性质”栏勾选“预付款”和“其他（联销等）”并填写“联销”
- **THEN** 风控结果保存“联销（预付款+联合销售）”及该表格行来源，不抽取相邻“业务模式简介”长文本，也不生成业务模式代码

#### Scenario: 审批样表缺少业务性质
- **WHEN** “业务性质”栏没有可确认的已勾选项，ApprovalFormExtractor 返回 raw_business_mode_text=MISSING
- **THEN** 风控结果保留 MISSING 状态，且不尝试从其他合同推断

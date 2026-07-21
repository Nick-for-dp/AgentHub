## ADDED Requirements

### Requirement: ERP 必须通过 internal 后端 adapter 访问

系统 SHALL 通过 `ErpRiskDataClient` 标准 port 查询 ERP。LangGraph、领域 service 和前端 MUST NOT 直接依赖 ERP 厂商 SDK、认证协议或构造厂商 HTTP 请求；凭证不得进入日志、响应、task result 或 invocation snapshot。

#### Scenario: graph 查询 ERP
- **WHEN** 正式风控图执行 ERP 查询节点
- **THEN** 节点通过标准 adapter 请求，并只接收平台 ERP query result

#### Scenario: external profile
- **WHEN** 系统以 external profile 启动
- **THEN** 真实 ERP client 不初始化，ERP 配置和路由不可用

### Requirement: ERP 查询必须保存不可变快照

每次 ERP 查询 MUST 保存 task、业务键、接口/schema 版本、查询时间、状态、脱敏 payload 或 URI、稳定 hash 和错误摘要。历史 snapshot MUST 只新增不覆盖；大 payload 转对象存储时仍必须保留 hash 和引用。

#### Scenario: ERP 后续修改金额
- **WHEN** 已完成任务引用的 ERP 金额在 ERP 中被后续修改
- **THEN** 历史任务仍引用原 snapshot，新任务查询生成新 snapshot

### Requirement: 文档事实、ERP 事实和人工决定必须独立

结果 SHALL 分别保存 document facts、ERP facts、ERP snapshot summary 和 comparisons/checks。ERP 值 MUST NOT 覆盖文档值、人工最终值或替 UNCERTAIN 文档字段选择候选；业务总览和 Excel 的文档来源值不得被 ERP 静默改写。

#### Scenario: ERP 与合同金额不同
- **WHEN** 文档采购金额为 10700000 而 ERP 采购金额为 10690000
- **THEN** 系统保留两值和来源并输出 MISMATCH，不把文档金额改为 ERP 金额

### Requirement: ERP comparison 必须使用稳定状态和通用证据契约

每条 comparison SHALL 输出 rule code/version、outcome、message、affected fields、DOCUMENT/ERP 两侧 value/unit/source、difference 和适用 tolerance。outcome MUST 至少支持 MATCHED、MISMATCH、ERP_MISSING、DOCUMENT_MISSING、ERP_UNAVAILABLE、NOT_COMPARABLE，并能被现有工作台通用 checks/evidence 直接展示。

#### Scenario: 金额一致
- **WHEN** 文档与 ERP 归一化采购金额均为 10700000.00
- **THEN** 系统输出 MATCHED、差异 0、规则版本和两侧证据

#### Scenario: ERP 超时
- **WHEN** adapter 有界重试后仍超时
- **THEN** 系统输出 ERP_UNAVAILABLE，不显示匹配通过或空白成功

### Requirement: 合同数量必须只与对应 ERP 事实核对

采购合同数量 SHALL 只与业务确认的 ERP 采购/收货数量核对，销售合同数量 SHALL 只与 ERP 销售/发货数量核对。系统 MUST NOT 自动比较采购合同数量和销售合同数量，也不得将二者不同视为 ERP 风险结论。

#### Scenario: 两份合同数量不同但 ERP 各自一致
- **WHEN** 采购合同为 2000 吨且 ERP 采购为 2000 吨，销售合同为 1980 吨且 ERP 销售为 1980 吨
- **THEN** 系统分别输出两条 MATCHED，不生成采购合同对销售合同的 MISMATCH

### Requirement: ERP 不可用必须按关键性 fail safe

认证失败、超时、响应 schema 错误、关键字段缺失或 ERP 功能关闭 MUST 形成稳定 warning/check。关键 ERP 核对不可完成时任务 MUST 按正式策略进入 WAITING_REVIEW；非关键项可 warning 后继续。任何不可用状态 MUST NOT 被序列化为 MATCHED。

#### Scenario: 关键采购金额无法查询
- **WHEN** ERP 返回成功响应但缺少策略定义的关键采购金额
- **THEN** 系统输出 ERP_MISSING 并进入 WAITING_REVIEW

### Requirement: 正式图必须替换演示图并复用同一人工复核链路

ERP 上线时系统 SHALL 升级 graph/schema/rule 版本，并在 build review items 前完成 snapshot、ERP facts 和 comparisons。人工复核后 SHALL 复用同一 ERP snapshot 重跑受影响 comparisons，不重复查询 ERP。演示任务/checkpoint MAY 在上线前清理或重新执行，不要求跨图恢复。

#### Scenario: 人工修正文档单价
- **WHEN** 用户在 ERP snapshot 已保存后修正文档采购单价
- **THEN** 同一 thread 使用原 snapshot 重跑受影响金额/ERP checks，不再次调用 ERP

### Requirement: ERP 接入不得要求重建工作台和 Excel

ERP 节点 SHALL 继续使用既有 task、review、通用 checks/evidence 和业务总览契约。系统 MUST NOT 为 ERP 接入复制工作台上传/复核页面或改变 Excel 只含“业务总览”sheet 的要求。

#### Scenario: 正式 ERP 任务完成
- **WHEN** 正式 LangGraph 产生 ERP comparisons 并完成任务
- **THEN** 现有工作台展示新增 checks，现有 Excel endpoint 仍生成相同业务总览结构

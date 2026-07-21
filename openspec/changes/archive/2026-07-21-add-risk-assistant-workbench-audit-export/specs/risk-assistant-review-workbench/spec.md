## ADDED Requirements

### Requirement: 风控工作台必须仅在 internal profile 可用

系统 SHALL 为已登录的 internal Cookie 用户注册风控助手工作台、任务详情和导航入口。external profile MUST 不注册这些路由或入口；前端 MUST NOT 直接调用 LangGraph、PaddleOCR、Qwen、Dify 或对象存储 SDK。

#### Scenario: external 构建不包含风控入口
- **WHEN** 前端以 external profile 构建
- **THEN** `/internal/risk-assistant` 路由、导航入口和页面懒加载均不存在

### Requirement: 工作台必须支持多文件任务提交

工作台 SHALL 支持 PDF/DOCX 多文件选择、每份文件的声明类型、预签名上传、独立上传进度、文件解析、单文件失败重试、业务编号输入和 risk task 创建。文件名 MUST 仅用于展示和弱提示，声明类型仍由用户选择并由后端内容级校验。

#### Scenario: 提交四文件业务包
- **WHEN** 用户上传采购合同、销售合同、审批表和结算单并完成类型声明
- **THEN** 页面将四个 SUCCEEDED file parse task 关联到同一个 PENDING 风控任务，并保留各自原始文件名

#### Scenario: 非标准合同文件名
- **WHEN** 用户上传名为“客户供货协议.pdf”的销售合同并声明 SALES_CONTRACT
- **THEN** 工作台允许提交，不要求文件名包含“01X销售合同”或固定编号

### Requirement: 工作台必须支持任务找回和刷新恢复

工作台 SHALL 展示当前用户拥有的轻量分页任务列表，并为每个任务提供稳定详情 URL。页面刷新或重新打开详情时 MUST 根据最新 task 状态恢复展示、轮询、人工复核或最终结果，不依赖浏览器内存保存唯一任务状态。

#### Scenario: 刷新待复核任务
- **WHEN** 用户在 `/internal/risk-assistant/tasks/{id}` 刷新 WAITING_REVIEW 任务
- **THEN** 页面重新 GET task 并恢复完整复核上下文，不创建新任务或重复 execute

### Requirement: 工作台必须使用稳定任务状态而非硬编码图节点

页面 SHALL 展示 PENDING、RUNNING、WAITING_REVIEW、SUCCEEDED、FAILED、CANCELLED 及耗时和错误。页面 MUST NOT 依赖固定 LangGraph 节点清单决定主流程；未知 current_node SHALL 降级显示为处理中。execute 或 review 响应不确定时 MUST 先查询任务状态再决定重试。

#### Scenario: ERP 图增加未知节点
- **WHEN** 后续 LangGraph 返回工作台未预先认识的 current_node 且 task 状态为 RUNNING
- **THEN** 页面继续显示处理中并轮询，不因节点名称变化报错或停止

### Requirement: 工作台必须展示业务总览和完整审计上下文

工作台 SHALL 以审计底稿 17 项业务总览为主表，并允许查看 canonical audit items、checks、warnings、来源文件原始名称、declared type、类型校验状态、page、quote、bbox、alternatives 和关联规则。WAITING_REVIEW 时 MUST 展示当前任务全部审计字段；非 review target MUST 只读。

#### Scenario: 货物名称等待复核
- **WHEN** 货物名称为当前 review target
- **THEN** 页面同时展示货物名称候选和证据、17 项业务总览，以及其余 FOUND/MISSING/UNCERTAIN 原子审计字段

### Requirement: 工作台必须以通用 checks 展示确定性核对

页面 SHALL 通用展示每条 check 的 code、outcome、message、affected fields 和 input evidence，不固定为文档/ERP/comparison 三列，也不得在 ERP 未接入时显示 MATCHED 或其它虚假对账状态。

#### Scenario: document-only 演示任务
- **WHEN** 当前结果只包含合同金额、比例、结算和日期等文档 checks
- **THEN** 页面展示这些 checks，且不显示空的 ERP 匹配结论

#### Scenario: 后续 ERP check
- **WHEN** 正式 LangGraph 使用相同 check/evidence 契约增加 ERP 核对结果
- **THEN** 现有工作台能够按通用 check 结构展示，不要求重建任务提交和复核页面

### Requirement: 工作台必须完成人工复核和同任务恢复

WAITING_REVIEW 页面 SHALL 展示当前 review item、候选、原值、来源、允许动作和必填原因。提交成功后 SHALL 恢复同一任务并防止重复提交；checkpoint 冲突 MUST 刷新任务并向用户明确提示。

#### Scenario: 人工修正字段
- **WHEN** 用户为当前 FIELD review item 输入修正值和原因
- **THEN** 页面提交 review、任务返回 RUNNING，并继续查询直至再次等待或终态

#### Scenario: checkpoint 已被更新
- **WHEN** review 请求返回 checkpoint version conflict
- **THEN** 页面刷新 task 和 review context，不自动重复提交旧决定

### Requirement: 来源证据必须真实可访问且不得伪造高亮

有权用户 SHALL 能查看 source 中的原始文件名、页码、quote、block id 和 bbox，并通过 AgentHub 授权接口获得短期原文件访问地址。前端 MUST NOT 暴露对象存储凭证；无法证明坐标对应关系时 MUST 显示 warning 而不是绘制近似高亮。

#### Scenario: 扫描 PDF 证据
- **WHEN** PaddleOCR source 包含第 2 页 quote 和 bbox，但没有浏览器坐标转换契约
- **THEN** 页面展示页码、quote、bbox 和原文件打开入口，不声称已精确框选

### Requirement: 工作台必须满足企业界面和响应式要求

页面 SHALL 使用 Ant Design Vue 和 AgentHub 蓝白规范，覆盖 loading、empty、error、WAITING_REVIEW 和终态。1366px MUST 支持业务总览与复核证据联动；1024px 和窄屏 MUST 收敛为抽屉、标签页或纵向布局，主要操作不得被遮挡。

#### Scenario: 1366px 待复核页面
- **WHEN** 用户在 1366px 桌面查看 WAITING_REVIEW 任务
- **THEN** 业务总览、当前复核操作和证据入口清晰可见且无文本溢出

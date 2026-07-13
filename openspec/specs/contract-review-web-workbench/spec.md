# contract-review-web-workbench

为 internal 部署提供合同上传、审查任务编排、敏感条款展示及原文联动高亮的 Web 工作台。

## Purpose

让已登录的 internal 用户通过 AgentHub API 完成 PDF/DOCX 合同上传、解析和合同审查，并在安全、可追溯的结果界面中复核敏感条款、规则依据、warnings 与原文位置；同时保持 external profile、Dify 凭证和 MinIO 长期凭证的边界隔离。

## Requirements

### Requirement: internal 用户可访问合同审查工作台

系统 SHALL 在 `DEPLOYMENT_PROFILE=internal` 的前端部署中提供需要登录的合同审查工作台，并使用现有 HttpOnly Cookie Session 访问 AgentHub internal API。该工作台 MUST NOT 直接持有或调用 Dify API Key、MinIO 长期凭证或底层文件解析能力；external profile MUST NOT 显示工作台入口。

#### Scenario: internal 用户登录后进入工作台

- **WHEN** 已登录的 internal 用户访问合同审查工作台路由
- **THEN** 系统展示合同上传和审查参数界面，并通过当前用户 Session 发起后续 AgentHub API 请求

#### Scenario: 未登录访问被拦截

- **WHEN** 未登录用户直接访问合同审查工作台路由
- **THEN** 前端将用户引导至登录页，且不发起文件上传、解析或合同审查请求

#### Scenario: external profile 不展示工作台

- **WHEN** 前端以 external profile 构建或运行
- **THEN** 导航和默认首页中不出现合同审查工作台，且不会将普通用户引导到 internal 合同审查路由

### Requirement: 用户可提交合同与审查参数

工作台 SHALL 提供单文件上传控件，并在开始审查前收集合同类型和合同对手方资信等级。首期可提交文件类型 MUST 限定为后端可直接解析的 PDF 或 DOCX；合同类型 MUST 明确映射为 `warehouse` 或 `transport`；资信等级 MUST 明确映射为 `A1` 至 `A7`。

#### Scenario: 完整输入可开始审查

- **WHEN** 用户选择一个 PDF 或 DOCX 文件，并选择合同类型与 A1-A7 资信等级
- **THEN** “开始审查”操作可用，且提交 payload 使用后端要求的稳定枚举值而非界面展示文案

#### Scenario: 不支持的文件在上传前被拒绝

- **WHEN** 用户选择 `.doc`、图片或其它非 PDF/DOCX 文件
- **THEN** 工作台在请求预签名 URL 前给出明确的格式错误，并保留用户重新选择文件的能力

#### Scenario: 缺少必填参数不能开始

- **WHEN** 文件、合同类型或资信等级任一项缺失
- **THEN** 工作台禁用开始操作并在对应控件附近说明缺失项

### Requirement: 工作台编排完整合同审查链路

前端 SHALL 通过 AgentHub API 按“申请预签名上传 → 上传文件 → 创建/查询解析任务 → 创建合同审查任务 → 显式执行/查询审查任务”的顺序完成一次审查。前端 MUST 只消费归一化任务响应，不得直接调用 Dify；每个阶段 MUST 展示稳定的进行中、成功或失败状态。

#### Scenario: 合同审查成功完成

- **WHEN** 上传、解析、任务创建和 execute 均成功
- **THEN** 工作台进入成功态，保存本次 `file_parse_task` 与 `contract_review_task` 的响应，并展示解析文本和结构化审查结果

#### Scenario: 中间阶段失败时停止后续调用

- **WHEN** 预签名上传、对象上传、文件解析或合同审查任务创建任一阶段失败
- **THEN** 工作台停止尚未开始的后续阶段，展示可理解且不含敏感凭证的错误，并允许用户安全地重试或重新选择文件

#### Scenario: execute 响应不确定时先查询任务

- **WHEN** execute 请求超时、断网或客户端未能确认响应，但请求可能已经到达后端
- **THEN** 工作台先 GET 查询合同审查任务终态，再决定展示结果或允许重试，MUST NOT 盲目重复 execute

#### Scenario: 任务接口返回非终态

- **WHEN** 文件解析或合同审查 API 返回 PENDING/RUNNING 等非终态
- **THEN** 工作台以有界轮询查询任务，直至成功、失败、取消或达到可配置超时，并在轮询期间展示当前阶段

### Requirement: 工作台展示解析合同内容

成功结果界面 SHALL 按 `file_parse_task.result_snapshot.blocks` 的原始顺序渲染合同解析文本，并显示可用于排障的 block 类型、章节标题或 block id。合同文本 MUST 作为纯文本渲染，不得作为未经净化的 HTML 注入页面。

#### Scenario: 按解析顺序展示合同

- **WHEN** 解析结果包含多个 blocks
- **THEN** 左侧合同视图按照数组顺序展示每个 block 的文本，并保留 block 的稳定 DOM 定位标识

#### Scenario: 解析结果为空或缺失

- **WHEN** 审查任务成功但解析快照缺少可展示 blocks
- **THEN** 工作台显示结果数据不完整提示，不伪造合同内容，且仍保留可用的审查摘要和条款排障信息

#### Scenario: 解析 warning 可复核

- **WHEN** `ParsedDocumentV1` 包含解析 warnings
- **THEN** 工作台在不遮挡正文的区域显示 warning 数量和详情入口

### Requirement: 敏感条款与解析文本联动高亮

工作台 SHALL 使用条款 `source_spans[]` 中的 `block_id`、`start_offset` 和 `end_offset` 在解析文本视图中生成高亮。offset MUST 按与后端 Python 字符索引一致的 Unicode code point 语义处理；高亮失败 MUST 转为可见 warning，不得通过模糊匹配静默标记可能错误的文本。

#### Scenario: 有效 source span 被高亮

- **WHEN** 敏感条款的 source span 指向存在的 block，offset 合法且片段可解析
- **THEN** 对应文本片段使用风险语义样式高亮，并可由条款卡片聚焦

#### Scenario: 点击条款定位原文

- **WHEN** 用户点击含有效 source span 的条款卡片
- **THEN** 合同视图滚动到首个对应 block，高亮片段获得短暂聚焦状态，且键盘操作也可触发同等行为

#### Scenario: source span 无法解析

- **WHEN** block 不存在、offset 越界、起止顺序错误、matched text 不一致或 spans 重叠导致某个片段不能安全渲染
- **THEN** 工作台保留该条款及其判定结果，显示条款级高亮 warning，并且不生成误导性的高亮

#### Scenario: 条款没有 source span

- **WHEN** 条款没有 `source_spans`，仅有 `source_block_ids` 或完全缺少来源位置
- **THEN** 工作台展示“无法精确高亮”的提示；若存在有效 source block，点击条款只定位到 block，不伪造字符级高亮

### Requirement: 结果界面完整呈现审查结论

工作台 SHALL 展示任务状态和 summary 指标，并为每条条款展示 `is_sensitive`、`risk_level`、`category`、原文、`matched_rules`、`reason`、`confidence` 与 warnings。默认视图 SHALL 突出敏感条款，同时允许用户查看全部已抽取条款；“未发现敏感条款” MUST 被视为有效业务结果而非执行失败。

#### Scenario: 展示敏感条款结果

- **WHEN** 审查结果包含一个或多个 `is_sensitive=true` 的条款
- **THEN** 工作台显示敏感条款数量、最高风险等级及条款详情，并用风险等级区分视觉样式

#### Scenario: 未发现敏感条款

- **WHEN** 审查任务 SUCCEEDED 且 `sensitive_clause_count=0`
- **THEN** 工作台显示“未发现敏感条款”的成功空状态，同时允许查看全部抽取条款和 warnings

#### Scenario: 顶层与条款级 warning 被保留

- **WHEN** 结果包含顶层 warnings 或条款 warnings
- **THEN** 工作台显示 warning 数量、所属条款和可读详情，不因存在 warning 将成功任务误显示为失败

### Requirement: 工作台具备可用的响应式与状态体验

工作台 SHALL 遵循 AgentHub 蓝白企业界面规范，优先使用 Ant Design Vue 组件，并覆盖初始、上传中、解析中、审查中、成功、无敏感条款和失败状态。桌面端 SHALL 提供合同与条款双栏复核；窄屏下 SHALL 转为不遮挡主要操作和错误信息的纵向布局。

#### Scenario: 桌面端双栏复核

- **WHEN** 用户在 1366px 或更宽的桌面视口查看成功结果
- **THEN** 合同正文与条款列表同时可见并各自可滚动，主要操作和摘要不发生文本溢出

#### Scenario: 窄屏结果仍可操作

- **WHEN** 用户在 1024px 或更窄视口查看工作台
- **THEN** 页面按断点收敛为可读布局，上传控件、状态、条款详情和定位操作不会互相遮挡

#### Scenario: 长时间审查有持续反馈

- **WHEN** 解析或 Dify workflow 执行时间超过普通请求等待时间
- **THEN** 工作台持续显示当前阶段和已耗时信息，避免用户误判页面无响应并重复提交


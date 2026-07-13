## MODIFIED Requirements

### Requirement: 按 agent.type 分发对话流处理器

平台 SHALL 维护**对话流**处理器注册表（ChatHandlerRegistry），按 `agent.type` 选择 **ChatHandler**。问答类 Agent（`AgentType.QA` 或未明确类型回退为问答）由 `QaChatHandler` 承载对话流逻辑。新增非问答**对话类** Agent 时 MUST 实现同一 ChatHandler 协议并在 ChatHandlerRegistry 登记，且无需改动通用 chat endpoint、`agent_invocation_record` 写入和产品会话协作逻辑。

ChatHandler 协议 MUST 只依赖平台自有类型（`AgentRuntimeChunk`、`AgentRuntimeRequest`、`Agent` 等），不得直接 import `app.integrations.dify.*`。

ChatHandlerRegistry MUST 为每次 chat 调用创建新的 handler 实例（工厂模式），禁止跨请求复用持有流式累积状态的 handler。

任务型 Agent（例如 `CONTRACT_REVIEW`）MUST NOT 注册为 ChatHandler 的静默回退目标；其执行走 TaskHandler 能力，不经由 `POST /api/v1/chat/{agent_code}` 的对话流协议。

#### Scenario: 问答 Agent 走问答 ChatHandler

- **WHEN** 调用 `POST /api/v1/chat/{agent_code}`，且该 Agent `type` 为问答类（或未指定回退为问答）
- **THEN** 平台选中 `QaChatHandler` 承载流式逻辑，SSE 事件结构（answer/thought/node/message_id/conversation_id/done/error）与重构前保持一致

#### Scenario: 未注册对话流 Agent 类型被拒绝

- **WHEN** 调用某 Agent，其 `type` 在 ChatHandlerRegistry 中不存在
- **THEN** 平台返回明确错误（不退化为问答 ChatHandler），并标识为不支持的 agent type；不产生半完成的 `agent_invocation_record`

#### Scenario: 新增对话类 Agent 类型不改 endpoint

- **WHEN** 后续新增一个非问答对话类 Agent 类型（例如结构化对话），并已在 ChatHandlerRegistry 登记其 ChatHandler
- **THEN** 该 Agent 通过同一 `POST /api/v1/chat/{agent_code}` 入口工作，endpoint 代码、调用记录写入与产品会话协作代码无需改动

#### Scenario: 并发请求 ChatHandler 状态隔离

- **WHEN** 两个并发 chat 请求分别 `select` 同一 agent type 的 ChatHandler
- **THEN** 两次 `select` 返回不同实例；各自累积的 answer / node_trace / runtime 快照互不影响

#### Scenario: 合同审查类型不走 chat 对话流

- **WHEN** Agent `type` 为 `CONTRACT_REVIEW` 且调用方误用 chat 入口或 ChatHandlerRegistry 查询该 type
- **THEN** ChatHandlerRegistry 不将其当作 QA 成功执行；合同审查执行 MUST 使用任务型 API 与 TaskHandler

## ADDED Requirements

### Requirement: ChatHandler 命名与任务型边界

平台文档与规格 MUST 将对话流处理器明确称为 ChatHandler（含 ChatHandlerRegistry、QaChatHandler），与 TaskHandler 并列。实现模块路径可保持 `modules/agent/handlers/`，但表述不得将任务型执行器称为 ChatHandler。

#### Scenario: 规格与模块说明使用 ChatHandler 用语

- **WHEN** 阅读 agent-handler-dispatch 能力说明或 handlers 包文档
- **THEN** 明确其为对话流 ChatHandler 抽象，并指向任务型能力由 TaskHandler 承担

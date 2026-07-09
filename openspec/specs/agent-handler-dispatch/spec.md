# agent-handler-dispatch

按 `agent.type` 分发对话流处理器（ChatHandler），使 chat endpoint 与调用记录/产品会话协作链路保持通用，不感知 runtime provider 专有类型。

## Purpose

支撑 ADR-014：在开发合同审查、报告抽取等 Agent 前补齐对话流编排抽象。问答类由 `QaChatHandler` 承载；新增非问答对话类 Agent 时注册新 handler 即可，无需改动 `POST /api/v1/chat/{agent_code}` 的通用链路。

## Requirements

### Requirement: 按 agent.type 分发对话流处理器

平台 SHALL 维护对话流处理器注册表，按 `agent.type` 选择处理器。问答类 Agent（`AgentType.QA` 或未明确类型回退为问答）由 `QaChatHandler` 承载对话流逻辑。新增非问答对话类 Agent 时 MUST 实现同一处理器协议并在注册表登记，且无需改动通用 chat endpoint、`agent_invocation_record` 写入和产品会话协作逻辑。

处理器协议 MUST 只依赖平台自有类型（`AgentRuntimeChunk`、`AgentRuntimeRequest`、`Agent`），不得直接 import `app.integrations.dify.*`。

注册表 MUST 为每次 chat 调用创建新的 handler 实例（工厂模式），禁止跨请求复用持有流式累积状态的 handler，以保证并发会话隔离。

#### Scenario: 问答 Agent 走问答处理器

- **WHEN** 调用 `POST /api/v1/chat/{agent_code}`，且该 Agent `type` 为问答类（或未指定回退为问答）
- **THEN** 平台选中 `QaChatHandler` 承载流式逻辑，SSE 事件结构（answer/thought/node/message_id/conversation_id/done/error）与重构前保持一致

#### Scenario: 未注册 Agent 类型被拒绝

- **WHEN** 调用某 Agent，其 `type` 在处理器注册表中不存在
- **THEN** 平台返回明确错误（不退化为问答处理器），并在 response 或 error 中标识为不支持的 agent type；不产生半完成的 `agent_invocation_record`

#### Scenario: 新增对话类 Agent 类型不改 endpoint

- **WHEN** 后续新增一个非问答对话类 Agent 类型（例如结构化对话），并已在注册表登记其处理器
- **THEN** 该 Agent 通过同一 `POST /api/v1/chat/{agent_code}` 入口工作，endpoint 代码、调用记录写入与产品会话协作代码无需改动

#### Scenario: 并发请求 handler 状态隔离

- **WHEN** 两个并发 chat 请求分别 `select` 同一 agent type 的 handler
- **THEN** 两次 `select` 返回不同 handler 实例；各自累积的 answer / node_trace / runtime 快照互不影响

### Requirement: 处理器协议不得泄漏 runtime provider

对话流处理器协议 MUST 只以 `AgentRuntimeChunk` / `AgentRuntimeRequest` / 平台自有归一化输出类型作为输入输出，不得把 `DifyChatChunk`、`NormalizedDifyOutput`、`DifyIntegrationError` 等 `app.integrations.dify.*` 专有类型暴露给 endpoint 或 handler 调用方。

#### Scenario: chat endpoint 不 import Dify 专有类型

- **WHEN** 检查 `backend/app/api/v1/endpoints/chat.py` 的 import 段
- **THEN** 不出现 `from app.integrations.dify.*`、不出现 `NormalizedDifyOutput` / `normalize_dify_final_output` / `DifyIntegrationError`

#### Scenario: runtime 错误以平台错误呈现

- **WHEN** runtime provider 返回 error
- **THEN** 处理器以平台自有错误类型上抛，endpoint 输出统一 `error` SSE 事件，不向客户端泄漏 Dify 原始敏感响应

### Requirement: 通用调用链保留调用记录与产品会话协作

处理器 MUST 与 endpoint 协作维护 `agent_invocation_record` 的 `retrieval` / `model` / `runtime` 三段快照结构（ADR-005 / ADR-013），并维护登录用户产品会话的创建、assistant 消息状态流转、`provider_conversation_id` 同步。客户端断开 MUST 将调用记录标记为 `FAILED` 且 `error_code=CLIENT_DISCONNECTED`。

#### Scenario: 调用记录三段快照保持稳定

- **WHEN** 完成一次问答 Agent 调用
- **THEN** `agent_invocation_record.snapshot` 仍含 `retrieval` / `model` / `runtime` 三个顶层子键，`runtime` 子键保留 `runtime_type`、`runtime_app_id`、`node_trace`、`dify_metadata`、`dify_final_output`、`lead_capture_result`（启用线索收集时）

#### Scenario: 客户端断开仍标记失败

- **WHEN** 客户端在流式响应过程中主动断开
- **THEN** 调用记录被更新为 `FAILED`，`error_code=CLIENT_DISCONNECTED`；assistant 消息状态更新为 `INTERRUPTED`（登录用户场景）

#### Scenario: 产品会话只服务登录用户

- **WHEN** 调用方为 API Key（非 `CallerType.USER`）
- **THEN** 不创建 `conversation` / `conversation_message`，仍写 `agent_invocation_record`

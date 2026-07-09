## Context

当前 `backend/app/api/v1/endpoints/chat.py` 是一个 ~210 行的 `event_stream` 闭包，把对话流消费、节点 trace 累积、Dify 输出归一化、产品会话写入、调用记录快照组装、线索收集全部焊死。它直接 `from app.integrations.dify.output import NormalizedDifyOutput, normalize_dify_final_output`，违反 PLAN.md P2 / ADR-014 验收「业务模块不再直接 import Dify 专有类型」。合同审查只能绕开通用链路另写 `backend/app/modules/contract_review/executor.py`，后续风控助手等新 Agent 类型若沿用现状会重复出现焊死 endpoint 的债。

已落地的部分（不在本设计重做）：
- `backend/app/modules/agent/runtime.py`：`AgentRuntime` Protocol、`AgentRuntimeChunk`、`DifyRuntime`、`AgentRuntimeService` registry、`_select_runtime`。
- `backend/app/integrations/dify/output.py`：`NormalizedDifyOutput` / `normalize_dify_final_output`（Dify 输出归一化，属于 `integrations/dify` 内部实现）。
- 调用记录快照三段 `retrieval` / `model` / `runtime`（ADR-005 / ADR-013）。

关心的红线（Agent.md §4/§5、DECISIONS ADR-001/014/018）：
- 业务模块、前端、外部客户不得直接调用 Dify；Dify 调用只在 `backend/app/integrations/dify`。
- 每次 runtime 调用必须有 `agent_invocation_record`；快照三段不改。
- 服务端会话与产品会话归属平台；Dify `conversation_id` 只作 `provider_conversation_id`。

## Goals / Non-Goals

**Goals:**
- chat endpoint 收敛为「鉴权 → 取 Agent → 选 handler → handler 透传 chunk 与结束信号 → endpoint 写调用记录与产品会话变更」，不再感知 Dify。
- 引入对话流 handler 协议，按 `agent.type` 分发；问答 handler 承载当前问答逻辑。
- Dify 输出归一化对 handler 调用方隐藏（下沉到 `integrations/dify/output` 的封装或问答 handler 内，不暴露给 endpoint / 后处理器）。
- 线索收集抽为可插拔后处理器，按 Agent 配置启用。
- 保持 SSE 事件结构、`StreamEvent`、`snapshot` 三段结构对外兼容。

**Non-Goals:**
- 不重做 `AgentRuntime` / `DifyRuntime` / registry。
- 不改合同审查 `executor.py` 独立链路。
- 不动 `/api/v1/internal/*`、不动数据库 schema、不写 Alembic。
- 不实现线索收集以外的新后处理器（评估、内容过滤等）。
- 不改 Dify SSE 解析逻辑。

## Decisions

### D1. handler 协议归属 `modules/agent/handlers/`，分层为 endpoint/service 之间

对照 Archi.md §4：当前「Runtime」模块只负责封装 Dify 调用与统一 chunk；chat endpoint 充当了「对话流编排」service 又混合了 endpoint 职责。本设计把「对话流编排」从 endpoint 下沉到 `modules/agent/handlers/`，属于 module service 层（Agent.md §7：endpoint 保持薄、业务编排放到 module service）。

`ChatHandler` 协议（Protocol/ABC）：
```
class ChatHandler(Protocol):
    def stream(self, agent, subject, chat_context) -> ChatStreamResult: ...
```
- `ChatContext`：聚合 `question`、`platform_conversation`、`provider_conversation_id`、`known_lead_state`、`subject`、`assistant_message` 等当前 endpoint 持有的上下文。
- `ChatStreamResult`：一个 async iterator of `AgentRuntimeChunk` + 一个 `Finalize` 回调（或 dataclass），由 endpoint 在流结束（成功/取消/异常）时调用，负责产出 `InvocationRecordFinish` 与产品会话更新。把 `_build_finish` 逻辑从闭包搬到 handler。

handler 只依赖 `AgentRuntimeService` + 平台自有类型；`QaChatHandler` 内部调用 `AgentRuntimeService.stream_chat`。

### D2. Dify 输出归一化封装在问答 handler，endpoint / 后处理器不感知

当前 `chat.py:22` 直接 import `NormalizedDifyOutput`/`normalize_dify_final_output`/`DifyIntegrationError`。设计：

- 平台新增「归一化输出」抽象（在 `modules/agent/` 内，例如 `NormalizedAgentOutput`），由 `QaChatHandler` 内部把 `integrations.dify.output.normalize_dify_final_output` 的结果转成平台抽象；后处理器只消费平台抽象。
- `DifyIntegrationError` 仍定义在 `integrations/dify`（它本就是 Dify 专有错误），handler 把它转成 `AgentHubError` 子类（如已有的 `DifyIntegrationError` 经由 endpoint 统一异常处理器呈现）——具体保留 `integrations/dify` 内的类，但 endpoint 不直接 import，由 handler 抛包后走 `register_exception_handlers`。
- 替代方案考虑过：把归一化放 `AgentRuntimeService`。否决理由：runtime 层应是 provider-agnostic 的流式协议，归一化是对「问答类」最终输出的语义化处理，属于问答 handler 职责，契约更窄。

### D3. 后处理器链：确定性顺序 + 失败隔离 + Agent 配置启用

- `Postprocessor` 协议：`process(agent, normalized_output, runtime_snapshot) -> PostprocessorResult`，只追加 `runtime_snapshot` 子键（如 `lead_capture_result`），不回调 runtime。
- `LeadCapturePostprocessor`：封装当前 `lead_service.capture_output` + `lead_capture_result.model_dump()`。
- 链调度器读 `agent.config_snapshot.get("postprocessors")`；问答 Agent 默认 [`"lead_capture"`]，非问答默认 `[]`。
- 异常隔离：每个后处理器 try/except，异常记录到 `runtime_snapshot["postprocessor_warnings"]`，不回滚调用状态。
- 替代方案考虑过：用 `agent.type` 直接决定后处理器集合而不读 config。否决理由：ADR-014 明确「线索收集等逻辑从 chat endpoint 抽为可插拔后处理器，按 Agent 配置启用」，写死类型耦合度更高；config 路径允许同类型 Agent 单独关闭线索收集（例如内部问答演示 Agent）。

### D4. 调用记录与产品会话协作仍由 endpoint 触发，handler 提供结果

为保持 `agent_invocation_record` 与产品会话的「单一写入源」，写入仍由 endpoint 在 handler 返回的 `Finalize` 回调里执行；handler 不直接写 invocation_service / conversation_service，避免两条写入路径。`Finalize` 接收 status（SUCCEEDED/FAILED/INTERRUPTED）和 overrides，产出 `InvocationRecordFinish` 三段快照。

### D5. 不改 runtime.py 的对外接口

`AgentRuntimeService.stream_chat` / `run_workflow` 签名不变，问答 handler 通过它消费 chunk。`AgentRuntime` Protocol 不动；handler 在 runtime 抽象之上。

## Risks / Trade-offs

- [重构面较大、回归风险] → 用现有 `test_chat_*` / `test_agent_runtime` / `test_lead_service` / `test_conversation_service` 作回归基线，重构保留 SSE 事件字段对字段比对；endpoint import 边界加静态测试。
- [后处理器配置语义可能被误用] → spec + design 明确「问答默认启用、非问答默认空、显式配置覆盖默认」；提供单元测试覆盖三类路径。
- [`NormalizedAgentOutput` 抽象可能过早] → YAGNI 风险；但当前唯一非 Dify runtime 尚未存在，抽象只容纳现有 `text` / `lead_deltas` 字段，不预设未来字段。
- [handler registry 与 runtime registry 职责重叠] → 两者不同：runtime 按 `runtime_type` 选 provider 实现（Dify/未来其他），handler 按 `agent.type` 选对话流编排；保持注册表分离。
- [迁移影响调用记录审计口径] → 三段子键、`node_trace`、`dify_metadata`、`dify_final_output`、`lead_capture_result` 位置和键名保持不变，并在测试中断言。
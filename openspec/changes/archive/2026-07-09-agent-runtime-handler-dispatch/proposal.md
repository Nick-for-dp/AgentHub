## Why

`PLAN.md` P2 / ADR-014「Agent runtime 抽象」的前半段已落地（`AgentRuntime` Protocol、`DifyRuntime`、`AgentRuntimeService` registry、`AgentRuntimeChunk`），但通用调用链路仍只服务问答场景：`backend/app/api/v1/endpoints/chat.py` 把对话流、节点 trace、Dify 输出归一化、产品会话写入、调用记录快照和线索收集全部焊死在单一 endpoint，且直接 `import` Dify 专有类型（`NormalizedDifyOutput`、`normalize_dify_final_output`、`DifyIntegrationError`），违反 P2 验收「业务模块不再直接 import Dify 专有类型」。合同审查只能绕开通用链路另写 `executor.py`，新增非问答 Agent 时无法按 `agent.type` 复用通用调用与审计逻辑。现在做是因为 PLAN-internal I6/I7 风控助手都将持续新增 Agent 类型，再不抽象会重复出现焊死 endpoint 的债。

## What Changes

- 引入对话流 handler 抽象：按 `agent.type` 分发处理器，回答问答（`AgentType.QA` 或当前默认类型）由 `QaChatHandler` 承载当前 `chat.py` 的流式逻辑，未来结构化对话 Agent 复用同一抽象。
- 把 `chat.py` 里 Dify 输出归一化（`normalize_dify_final_output`、`NormalizedDifyOutput`）从 endpoint 直接依赖下沉到问答 handler 或 `integrations/dify/output` 的封装背后；endpoint 不再 import `integrations.dify.*`。
- 把线索收集（`LeadService.capture_output` + `lead_capture_result` 写入 `snapshot.runtime`）从 chat 流硬编码抽为可插拔后处理器链，按 Agent 配置（`config_snapshot.postprocessors` 或等价元数据）启用；问答 Agent 默认启用线索收集，其他类型默认关闭。
- `chat.py` 的 endpoint 收敛为：鉴权 → 取 Agent → 选 handler → handler 透传 chunk 与结束信号 → endpoint 负责写 `agent_invocation_record` 与产品会话变更；快照 `retrieval` / `model` / `runtime` 三段结构保持不变（ADR-005、ADR-013）。
- 同步 `PLAN.md` P2 状态（标注前半已完成、本提案收口后半），并在 `Archi.md` 描述新增 handler 抽象边界。**不改动** `DECISIONS.md` ADR-014 内容（决策已立，仅落地）。
- **Non-goals**：
  - 不重做已落地的 `AgentRuntime` / `DifyRuntime` / registry（已在 `runtime.py`）。
  - 不改动合同审查现有 `executor.py` 独立链路；其未来若改走 handler 抽象另立提案。
  - 不引入风控助手、不动 `/api/v1/internal/*` 路由、不动数据库 schema、不涉及 Alembic。
  - 不在本提案内做线索收集后处理器以外的后处理器实现（如评估、内容过滤）。
  - 不修改 Dify SSE 解析逻辑（`integrations/dify/schemas.py`、`client.py`）。

## Capabilities

### New Capabilities

- `agent-handler-dispatch`: 平台按 `agent.type` 分发对话流处理器，承载 stream chunk 累积、节点 trace、产品会话与调用记录快照协作；新增 Agent 类型无需改动通用 chat endpoint 与审计链路。
- `chat-postprocessors`: chat endpoint 内联的 Dify 归一化、线索收集抽为可插拔后处理器链，按 Agent 配置启用；后处理器只消费统一 chunk 与归一化输出，不感知 runtime provider。

### Modified Capabilities

无（`openspec/specs/` 当前为空，本提案为首批能力沉淀）。

## Impact

- 受影响代码：
  - `backend/app/api/v1/endpoints/chat.py`（核心重构，endpoint 变薄）。
  - `backend/app/modules/agent/runtime.py`（可能新增 handler 注册表入口，`AgentRuntimeService` 接口规模保持不变）。
  - 新增 `backend/app/modules/agent/handlers/`（问答 handler + 后处理器接口与线索收集实现）。
  - `backend/app/modules/lead/service.py`、`backend/app/integrations/dify/output.py` 仅作为被后处理器调用的依赖，契约不变。
- 受影响 API：`POST /api/v1/chat/{agent_code}` 行为与 SSE 事件结构保持兼容（`StreamEvent` 不变），不视为 BREAKING；调用记录 `snapshot.runtime` 子键结构与 `retrieval` / `model` / `runtime` 三段保持不变。
- 依赖：无新增第三方依赖。
- 测试：现有 `test_chat_*`、`test_agent_runtime.py`、`test_lead_service.py`、`test_conversation_service.py` 必须全绿，并补充 handler 分发、后处理器开关、endpoint 不再 import Dify 类的边界测试。
- 文档：同步 `Archi.md`（handler 抽象边界）和 `PLAN.md` P2 状态；本提案归档后沉淀到 `openspec/specs/` 两个新能力。
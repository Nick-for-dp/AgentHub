## 1. 对话流 handler 抽象骨架

- [x] 1.1 在 `backend/app/modules/agent/handlers/__init__.py` 定义 `ChatHandler` Protocol、`ChatContext` 与 `Finalize`/`ChatStreamResult` dataclass；协议只依赖 `AgentRuntimeChunk` / 平台自有类型，不 import `app.integrations.dify.*`
- [x] 1.2 新增 handler 注册表，按 `agent.type` 分发；未注册类型返回明确错误（不退化为问答）；未指定 type 问答回退；注册工厂每次 `select` 创建新实例保证并发会话隔离
- [x] 1.3 单元测试：分发命中问答、未注册类型被拒、回退为问答三条路径

## 2. 归一化输出平台抽象 + QaChatHandler

- [x] 2.1 在 `modules/agent/` 内新增平台归一化输出类型 `NormalizedAgentOutput`（只含当前所需的 `text` / `lead_deltas` / `to_public_dict`），不暴露 Dify 类型
- [x] 2.2 实现 `QaChatHandler`：承载当前 `chat.py` `event_stream` 内 chunk 消费、`node_trace` 累积、provider_conversation_id 同步、`_build_finish` 快照组装逻辑；内部调用 `normalize_dify_final_output` 并转为 `NormalizedAgentOutput`
- [x] 2.3 把 `DifyIntegrationError` 转为 endpoint 经 `register_exception_handlers` 统一呈现，endpoint 不再直接 import 该类
- [x] 2.4 单元测试：QaChatHandler 累积 answer/`node_trace`、`provider_conversation_id` 同步、错误路径产出 FAILED 快照

## 3. 可插拔后处理器链

- [x] 3.1 定义 `Postprocessor` 协议与调度器；读 `agent.config_snapshot.get("postprocessors")`；问答默认 `["lead_capture"]`、非问答默认 `[]`、显式配置覆盖默认
- [x] 3.2 实现 `LeadCapturePostprocessor`：封装 `LeadService.capture_output` + `lead_capture_result.model_dump()` 写入 `snapshot.runtime`
- [x] 3.3 后处理器异常隔离：单个后处理器抛异常被捕获，记录到 `snapshot.runtime["postprocessor_warnings"]`，不回滚调用 SUCCEEDED
- [x] 3.4 单元测试：问答默认启用线索、非问答默认关闭、显式配置覆盖、线索后处理器异常不影响 SUCCEEDED 四条路径
- [x] 3.5 边界测试：线索收集后处理器模块 import 段不出现 `from app.integrations.dify.*`

## 4. chat endpoint 收敛重构

- [x] 4.1 重写 `chat.py` endpoint：鉴权 → 取 Agent → 鉴权 embed/权限 → 选 handler → handler 返回 stream + finalize → endpoint 执行 StreamingResponse，逐 chunk yield SSE
- [x] 4.2 `agent_invocation_record` 写入与产品会话 `assistant_message` 状态迁移仍由 endpoint 在 finalize 阶段执行，保持单一写入源
- [x] 4.3 客户端断开 (`asyncio.CancelledError`) 仍走 FAILED + `CLIENT_DISCONNECTED`，assistant 消息 `INTERRUPTED`
- [x] 4.4 边界测试：`chat.py` import 段不含 `app.integrations.dify`、`NormalizedDifyOutput`、`normalize_dify_final_output`、`DifyIntegrationError`

## 5. 调用记录与产品会话回归

- [x] 5.1 回归测试：一次成功调用 `snapshot` 含 `retrieval` / `model` / `runtime` 三段，`runtime` 子键（`runtime_type`、`runtime_app_id`、`node_trace`、`dify_metadata`、`dify_final_output`、`lead_capture_result`）键名键值与重构前一致
- [x] 5.2 回归测试：SSE 事件字段集（answer/thought/node/message_id/conversation_id/done/error）与重构前对字段比对一致；`StreamEvent` 前端契约不变
- [x] 5.3 回归测试：API Key 调用不创建 `conversation` / `conversation_message`，仍写 `agent_invocation_record`
- [x] 5.4 回归测试：embed session 越权 Agent 返回 403；权限不足返回 403
- [x] 5.5 运行既有 `test_chat_*` / `test_agent_runtime.py` / `test_lead_service.py` / `test_conversation_service.py` 全绿，并补足 handler 分发、后处理器开关与 endpoint import 边界新增测试（本地全量 `351 passed`）

## 6. 文档同步

- [x] 6.1 更新 `Archi.md`：在模块职责表（§4）补「Agent Handlers」一行，说明按 `agent.type` 分发对话流编排、位于 `modules/agent/handlers/`；§5 关键运行流程中 Q&A 流程描述同步
- [x] 6.2 更新 `PLAN.md` P2：标注 `AgentRuntime` / `DifyRuntime` / registry 已完成（前半），handler 分发与可插拔后处理器由本 change 收口（后半），并标记剩余项为完成
- [x] 6.3 更新 `CHANGELOG.md`：追加本变更摘要
- [x] 6.4 `DECISIONS.md` 无需新增 ADR（ADR-014 已覆盖，仅落地）；在 change README 或 proposal 中明确引用 ADR-014

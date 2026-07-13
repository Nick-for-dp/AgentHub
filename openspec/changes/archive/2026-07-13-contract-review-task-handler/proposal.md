## Why

对话流侧已通过 OpenSpec change `agent-runtime-handler-dispatch` 落地 `ChatHandler` + 可插拔后处理器（ADR-014 后半段），但合同审查仍走独立的 `ContractReviewExecutionService` / endpoint 硬编排：虽已调用 `AgentRuntimeService.run_workflow`，却没有与对话流对称的「按 `agent.type` 分发的任务型 handler」抽象，执行步骤也未拆成可扩展的前处理 / 核心处理 / 后处理流水线，后续增加校验、富化、规则或导出步骤时容易继续焊死在单一 `execute_task` 里。`PLAN-internal.md` 合同审查主链路与后续风控助手需要可复用的任务型调用模式；现在做是为了在扩大内部 Agent 类型前收口 L1–L5 对齐，并预留 TaskHandler 步骤级扩展空间。

本提案对应：`PLAN-internal.md` 合同审查调用结构对齐（承接 ADR-014 任务型扩展）；并澄清对话流 handler 命名为 **ChatHandler**（与 TaskHandler 并列）。

**鉴权前提（保持不变）：** 合同审查是 internal profile 下的**系统集成接口**，调用方以 **API Key（`Authorization: Bearer`）** 为主完成认证；具备合同审查权限的 Key 必须带有 scope `agent:contract_review:invoke`（或通配 `*`）。任务归属与 `api_key_id` / 组织绑定。本 change 只重构执行编排，**不弱化、不绕过**上述鉴权与 scope 模型。

## What Changes

- **新建任务型抽象 `TaskHandler` + `TaskHandlerRegistry`**，落在 `backend/app/modules/agent/task_handlers/`；按 `agent.type` 工厂分发，每次 execute 新建实例。
- **TaskHandler 执行模型强制为可插拔流水线**，步骤隔离为至少三段：
  1. **前处理（preprocess）**：任务就绪校验、归属/类型校验、从 file_parse 等加载上下文、组装 workflow 输入等；
  2. **核心处理（core）**：当前即经 `AgentRuntimeService` 调用 Dify/workflow（`run_workflow`），是唯一权威的模型/工作流调用点；
  3. **后处理（postprocess）**：抽取结果归一化、确定性规则判敏、高亮定位、组装业务 result 与 invocation snapshot 等。  
  各阶段 MUST 在代码结构上可独立替换/增补（协议或注册链），禁止把前/核/后揉进不可拆的单函数泥球。
- **合同审查**实现 `ContractReviewTaskHandler`：按上述三段编排；领域细节（规则、高亮、输入输出解析）仍留在 `modules/contract_review/`，由各阶段委托调用。
- **鉴权与授权保持 API Key 模型**：endpoint 继续经 `get_current_subject` 认证；创建/执行等写路径对 API Key 强制校验 `agent:contract_review:invoke`（或 `*`）；查询/取消/执行校验任务归属（含 `api_key_id`）。TaskHandler 只接受已鉴权的 `AuthenticatedSubject`，不自行解析凭证。
- **明确对话流侧命名为 ChatHandler**：文档与主规格用语统一；合同审查不进 ChatHandlerRegistry，不走 `/chat`。
- **保持现有 internal API 与 B 方案**：create 只落 PENDING，execute 再触发流水线。
- **对齐深度 L1–L5**：Runtime 仅经 `AgentRuntimeService`；类型分发；归一化边界；调用记录三段 snapshot；规则引擎落在后处理阶段。
- **CRUD 命名澄清**：`ContractReviewHandler` → 应用服务（如 `ContractReviewService`）。
- 同步 `Archi.md` / `PLAN-internal.md` / `CHANGELOG.md`；**不新增 ADR**（延续 ADR-014）。
- **Non-goals**：
  - 不改 external chat SSE 契约。
  - 不把合同审查并入 `/chat`。
  - 不实现风控 TaskHandler、不引入 arq 生产调度（可预留同一 execute 入口）。
  - 不改 schema / Alembic；不改 Dify workflow 定义；不把判敏权威上移到 Dify。
  - **不改为「匿名可调」或去掉 API Key scope**；不把合同审查主调用方改成浏览器用户 Cookie 会话（Cookie 若被依赖层接受，仍须满足既有归属规则，且不以本 change 扩展为面向 C 端开放）。
  - 本 change **不要求**一次实现通用配置化「任意插件市场」；要求结构可插拔，合同审查先落地固定阶段实现，后续 Agent 可增补阶段实现。

## Capabilities

### New Capabilities

- `agent-task-handler-dispatch`: 平台按 `agent.type` 分发 TaskHandler；执行模型为可插拔前处理 / 核心处理（runtime workflow）/ 后处理流水线；写出 `agent_invocation_record` 三段快照；不进入 chat SSE。
- `contract-review-task-execution`: 合同审查在 B 方案下由 TaskHandler 流水线执行：前处理校验与组输入、核心 `run_workflow`、后处理抽取+规则+高亮与落库；**API Key 鉴权 + scope + 归属**保持；HTTP 契约兼容。

### Modified Capabilities

- `agent-handler-dispatch`: 明确仅覆盖**对话流 ChatHandler**；与 TaskHandler 并列；任务型 MUST NOT 注册为 Chat 回退。

## Impact

- 受影响代码：
  - 新增 `backend/app/modules/agent/task_handlers/`（协议、阶段抽象、注册表、`ContractReviewTaskHandler`）。
  - `contract_review/executor.py` 迁入/委托流水线；`handlers.py` CRUD 重命名（**保留** `_assert_contract_review_scope` 与归属校验语义）。
  - `internal/contract_review.py` execute 选 TaskHandler；仍 `Depends(get_current_subject)`。
  - ChatHandler 文档澄清；可选中性化 `dify_input`/`dify_output` 命名。
- API：internal contract-review **非 BREAKING**（含鉴权方式：Bearer API Key + scope）。
- 测试：鉴权/scope/归属、阶段隔离、registry、B 方案、规则判敏、失败落库、与 Chat 不串台。
- 文档：Archi / PLAN-internal / CHANGELOG；归档后沉淀 main specs。

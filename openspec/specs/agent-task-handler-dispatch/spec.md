# agent-task-handler-dispatch

按 `agent.type` 分发任务型处理器，并以可插拔的前处理、核心处理和后处理流水线承载任务型 Agent 的执行。

## Purpose

为合同审查等非对话型 Agent 提供与 ChatHandler 隔离的统一任务执行扩展点，保持 endpoint、runtime provider 与领域后处理之间的清晰边界。

## Requirements

### Requirement: 按 agent.type 分发任务型处理器

平台 SHALL 维护任务型处理器注册表（TaskHandlerRegistry），按 `agent.type` 选择处理器。注册表 MUST 使用工厂模式，为每次任务执行创建新的 handler 实例。处理器协议 MUST 只依赖平台自有类型与领域上下文，不得直接 import `app.integrations.dify.*` 客户端或专有 chunk 类型。

合同审查（`AgentType.CONTRACT_REVIEW`）MUST 注册对应 TaskHandler。未注册的 agent type MUST 返回明确错误，不得回退为对话流 ChatHandler，也不得静默当作合同审查执行。

#### Scenario: 合同审查 agent 选中合同审查 TaskHandler

- **WHEN** 执行合同审查任务且任务绑定的 Agent `type` 为 `CONTRACT_REVIEW`
- **THEN** 平台通过 TaskHandlerRegistry 选中合同审查 TaskHandler 并执行，且该实例不与其它并发执行共享可变状态

#### Scenario: 未注册任务型 agent type 被拒绝

- **WHEN** 执行路径加载的 Agent `type` 未在 TaskHandlerRegistry 注册
- **THEN** 平台返回明确错误，不调用 runtime workflow，不将业务任务错误地标为 SUCCEEDED

#### Scenario: 任务型与对话流注册表隔离

- **WHEN** 某 agent type 仅注册在 TaskHandlerRegistry
- **THEN** 该 type 不得因 ChatHandlerRegistry 未命中而被当作 QA 对话处理；反之 ChatHandler 未注册 type 也不得落入 TaskHandler

### Requirement: TaskHandler 执行必须为可插拔阶段流水线

TaskHandler 的一次执行 MUST 在代码结构上隔离为可扩展阶段，至少包含：

1. **前处理（preprocess）**：就绪校验、上下文加载、workflow 输入组装等，在调用 runtime 之前完成；
2. **核心处理（core）**：经 `AgentRuntimeService`（或等价平台 runtime 门面）触发模型/工作流；当前合同审查核心即为 Dify workflow 调用；
3. **后处理（postprocess）**：结果归一化、确定性业务规则、高亮或其它领域步骤、组装业务结果与调用记录快照素材。

阶段 MUST 可被替换或增补而不改动通用 endpoint。禁止将前处理、核心处理、后处理耦合为无法单独测试的单一不可拆函数作为唯一实现形态。核心处理 MUST NOT 承担敏感条款判定等应属后处理的确定性业务规则权威。

#### Scenario: 前处理失败不进入核心处理

- **WHEN** 前处理阶段判定任务不可执行（例如非 PENDING 或 file_parse 未成功）
- **THEN** 系统不调用 runtime workflow，不将任务标为 SUCCEEDED

#### Scenario: 核心处理仅通过 AgentRuntime

- **WHEN** TaskHandler 需要调用 Dify/workflow
- **THEN** 调用发生在核心处理阶段且经由 `AgentRuntimeService`，业务模块不直接使用 Dify HTTP 客户端

#### Scenario: 后处理可在不改 endpoint 的前提下扩展

- **WHEN** 为某 TaskHandler 增加一个新的后处理步骤实现并挂入该 handler 的后处理序列
- **THEN** 通用任务执行 endpoint 无需修改即可在执行路径中运行该步骤（由 handler 组装决定）

### Requirement: 任务型调用必须写调用记录

每次真正触发 runtime 核心处理的执行 MUST 创建并完成一条 `agent_invocation_record`，快照 MUST 包含 `retrieval` / `model` / `runtime` 三个顶层子键。

#### Scenario: 成功执行写入 SUCCEEDED 调用记录

- **WHEN** TaskHandler 成功完成核心处理与必需的后处理
- **THEN** 对应 `agent_invocation_record` 状态为 SUCCEEDED，且 snapshot 含 retrieval/model/runtime

#### Scenario: 失败执行写入 FAILED 调用记录

- **WHEN** 核心处理或必需后处理抛错导致任务失败
- **THEN** 调用记录标记 FAILED 并记录错误信息，业务任务进入 FAILED（或产品定义的失败态），不得留下永久 RUNNING 且无终态记录

### Requirement: 任务型确定性后处理

任务型 Agent 在核心处理返回结构化结果后，SHALL 在后处理阶段运行平台侧确定性逻辑（例如规则引擎、高亮定位）。该阶段 MUST 在 AgentHub 后端执行，不得把敏感条款判定等规则结论交给 LLM/Dify 作为唯一权威。后处理与 chat 可插拔后处理器在「可插拔/可编排」语义上对齐，但失败策略可由领域定义（主产物失败可导致任务 FAILED）。

#### Scenario: 合同审查规则判敏在后端后处理完成

- **WHEN** 合同审查 TaskHandler 在核心处理后获得条款抽取列表
- **THEN** 敏感与否、风险等级、命中规则由后端规则引擎在后处理阶段生成并写入业务结果，而非仅依赖模型自由文本结论

### Requirement: RISK_ASSISTANT 必须注册独立 TaskHandler

TaskHandlerRegistry SHALL 为 AgentType.RISK_ASSISTANT 注册工厂并每次创建新实例。该类型 MUST 不回退为 QA 或 CONTRACT_REVIEW。

#### Scenario: 风控任务选择 handler
- **WHEN** 执行 RISK_ASSISTANT 任务
- **THEN** registry 返回新的 RiskAssessmentTaskHandler

### Requirement: TaskHandler 可选支持暂停和恢复

TaskHandler 模板 SHALL 提供可选 suspended/resume 扩展点。暂停不得调用成功/失败 finalize；恢复 MUST 复用任务和 invocation。未启用该能力的 handler MUST 保持原行为。

#### Scenario: 合同审查不受影响
- **WHEN** CONTRACT_REVIEW handler 完成或失败
- **THEN** 它继续直接 finalize，且无需实现 resume

#### Scenario: 风控暂停
- **WHEN** 风控图 interrupt
- **THEN** handler 持久化 WAITING_REVIEW，不把 invocation 标记成功

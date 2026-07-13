# contract-review-task-execution

通过已鉴权的任务型 API 和 TaskHandler 流水线执行合同审查，保持任务生命周期、归属、调用记录及结构化结果契约稳定。

## Purpose

为合同审查提供安全、可审计且可扩展的执行链路，将 Dify workflow 调用与平台侧确定性规则、高亮后处理清晰分离。

## Requirements

### Requirement: API Key 鉴权与合同审查 scope

合同审查 internal API SHALL 要求调用方通过平台统一认证依赖（`get_current_subject`）完成认证。面向系统集成的主调用方式 MUST 为 **API Key**（`Authorization: Bearer <api_key>`）。使用 API Key 创建合同审查任务时，Key 的 scopes MUST 包含 `agent:contract_review:invoke` 或通配 `*`；否则 MUST 拒绝（403 或等价禁止错误）。

TaskHandler 流水线 MUST 仅在已认证且通过归属校验的主体上下文中执行，MUST NOT 提供绕过 API Key / scope 的执行入口。查询、取消、执行 MUST 校验任务归属（含 `api_key_id` / 用户 / 组织既有规则），越权 MUST 拒绝且 MUST NOT 触发 runtime。

#### Scenario: 无认证凭证拒绝访问

- **WHEN** 调用方未提供有效 API Key（或其它平台接受的认证凭证）访问合同审查接口
- **THEN** 请求被拒绝（401 或等价未认证错误），不创建任务、不执行流水线

#### Scenario: API Key 缺 scope 拒绝创建

- **WHEN** 调用方使用有效 API Key，但其 scopes 既不包含 `agent:contract_review:invoke` 也不包含 `*`
- **THEN** 创建合同审查任务被拒绝（403 或等价禁止错误）

#### Scenario: 具备 scope 的 API Key 可创建任务

- **WHEN** 调用方使用具备 `agent:contract_review:invoke`（或 `*`）的 API Key 创建合同审查任务且 file_parse 已成功
- **THEN** 系统创建 PENDING 任务，并将 `api_key_id`（及既有 org/user 字段）记入任务以便归属与审计

#### Scenario: 越权不能执行他人任务

- **WHEN** 主体尝试 execute 不属于自己的任务
- **THEN** 返回禁止/未找到策略下的拒绝，不触发 runtime

### Requirement: B 方案任务生命周期保持兼容

合同审查 HTTP API SHALL 保持 create 仅创建 `PENDING` 业务任务、显式 execute（或未来 worker 调用同一执行入口）才触发 TaskHandler 流水线的 B 方案。`POST/GET /api/v1/internal/contract-review/tasks`、`POST .../cancel`、`POST .../execute` 的对外路径与主要响应字段 MUST 保持兼容（非 BREAKING）。上述接口均 MUST 在已认证主体下访问。

#### Scenario: 创建任务不触发 runtime

- **WHEN** 已鉴权且具备 scope 的调用方创建合同审查任务且引用已成功的 file_parse_task
- **THEN** 系统落库 PENDING 任务并返回 task id，不创建成功态的 agent_invocation_record，不调用 Dify workflow

#### Scenario: 仅 PENDING 可执行

- **WHEN** 对非 PENDING 任务调用 execute
- **THEN** 系统拒绝执行并返回冲突/明确错误，不重复触发 runtime

#### Scenario: 取消仅影响 PENDING

- **WHEN** 对 PENDING 任务调用 cancel
- **THEN** 任务变为 CANCELLED；对已终态任务取消被拒绝或不产生副作用（与现行为一致）

### Requirement: execute 经可插拔 TaskHandler 流水线完成审查

`POST .../tasks/{task_id}/execute` SHALL 在已认证主体下加载任务与 Agent，校验归属后经 TaskHandlerRegistry 选择合同审查 TaskHandler，并按 **前处理 → 核心处理 → 后处理** 执行：

1. **前处理**：归属与就绪校验、加载解析上下文、组装 workflow 输入；
2. **核心处理**：`AgentRuntimeService.run_workflow`（当前 Dify workflow）；
3. **后处理**：条款抽取归一化、规则判敏、高亮、更新 `contract_review_task` 与 `agent_invocation_record` 素材并 finalize。

endpoint MUST 保持薄：不得直接 import `app.integrations.dify.*`，不得在 endpoint 内实现规则判敏或组 workflow 大输入；不得省略 `get_current_subject` 认证依赖。

#### Scenario: 解析未成功不能进入核心处理

- **WHEN** 任务引用的 file_parse_task 非 SUCCEEDED
- **THEN** 前处理失败，execute 被拒绝或任务失败且不调用 runtime

#### Scenario: 成功返回结构化 result

- **WHEN** 三阶段成功完成
- **THEN** 任务状态为 SUCCEEDED，`result` 含条款列表、summary、warnings 等既有结构字段，并关联 `invocation_record_id`

#### Scenario: agent 类型不匹配被拒绝

- **WHEN** 任务 `agent_code` 对应 Agent 的 type 不是 CONTRACT_REVIEW 或未注册 TaskHandler
- **THEN** 执行失败并给出明确错误，不把错误类型当作问答 ChatHandler 处理

#### Scenario: 后处理规则判敏写入 result

- **WHEN** 核心处理返回可解析的条款抽取
- **THEN** 后处理规则引擎输出敏感标记/风险等级等写入任务 result，而非 endpoint 自行计算

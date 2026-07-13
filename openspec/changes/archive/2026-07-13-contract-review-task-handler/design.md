## Context

对话流已具备 **ChatHandler** + 可插拔后处理器。合同审查走 internal 任务 API + `ContractReviewExecutionService.execute_task`：L1（`run_workflow`）基本到位，但执行逻辑是单体函数，前处理（校验/组输入）、核心（workflow）、后处理（抽取/规则/高亮/落库）未隔离，后续加步骤只能继续堆在 `execute_task` 内。`ContractReviewHandler` 命名与平台 handler 混淆。

**鉴权现状（本 change 必须保持）：**

| 项 | 现状 |
|---|---|
| 路由 | `/api/v1/internal/contract-review/*`，仅 **internal** deployment profile 注册 |
| 认证 | endpoint `Depends(get_current_subject)`：支持 `Authorization: Bearer <API Key>`（及平台统一的其它凭证形态） |
| 主调用方 | **企业/内部系统集成 → API Key** |
| 授权 scope | 创建等写路径：`agent:contract_review:invoke` 或 scopes 含 `*`（常量 `CONTRACT_REVIEW_INVOKE_SCOPE`） |
| 归属 | 任务记录 `api_key_id` / `created_by` / `owner_org_unit_id`；get/cancel/execute 校验主体与任务归属 |
| 与 chat 差异 | 问答可面向登录用户 Cookie；合同审查 **不以 C 端用户会话为主路径**，重构不得削弱 API Key + scope |

分层对照 Archi.md：

| 层 | 现状 | 本设计 |
|---|---|---|
| endpoint | internal contract_review 已较薄 | 仍薄：`get_current_subject` → CRUD 或 select TaskHandler → 返回 task |
| authz | scope + 归属在 CRUD handler | 保留在 `ContractReviewService` / 前处理；TaskHandler 接收已鉴权 subject |
| module service | CRUD Handler + ExecutionService | CRUD → `ContractReviewService`；执行 → TaskHandler 流水线 |
| pipeline stages | 揉在 executor | preprocess / core / postprocess 可插拔隔离 |
| domain | rules / highlight / input-output | 仍属 `contract_review/`，由阶段委托 |
| runtime | `AgentRuntimeService` | **仅** core 阶段调用 |
| integration | `integrations/dify` | 仅 runtime 触达 |

约束：internal profile；**API Key + scope**；每次真正 run_workflow 写 invocation；LLM 只抽取，判敏在后端；B 方案 create/execute 分离。

## Goals / Non-Goals

**Goals:**

- 建立 `TaskHandler` + `TaskHandlerRegistry`（`modules/agent/task_handlers/`）。
- **强制可插拔流水线**：前处理 / 核心处理 / 后处理结构隔离；核心处理当前 = Dify/workflow via `AgentRuntimeService`。
- 合同审查 `ContractReviewTaskHandler` 按三段落地，对齐 L1–L5。
- **保持 API Key 鉴权与 `agent:contract_review:invoke` scope、任务归属语义**。
- ChatHandler 命名澄清；任务型不进 Chat 注册表。
- CRUD 去歧义命名；HTTP 契约兼容；预留 worker 复用 execute。

**Non-Goals:**

- 不改 chat SSE、不合并 `/chat`。
- 不实现风控 TaskHandler / arq 队列。
- 不改 schema、不改 Dify workflow 定义。
- 不把规则引擎做成跨域通用 DSL。
- **不取消 API Key / scope 要求，不改为公开匿名接口。**
- 不在本 change 实现「配置驱动动态加载任意插件」的插件市场；只保证**代码结构可增补阶段实现**。

## Decisions

### D1. TaskHandler 与 ChatHandler 并列

- **ChatHandler**：`stream` + `build_finish`，SSE + 会话。
- **TaskHandler**：`execute(ctx)` 驱动**阶段流水线**，业务任务状态机 + invocation；无 SSE 义务。

否决共用「AgentHandler」超协议。

### D2. 可插拔流水线（本 change 核心补充）

TaskHandler 的 `execute` MUST 编排固定顺序的阶段，而不是单块业务脚本：

```text
execute(ctx)
  → 进入 RUNNING / 创建 invocation（编排层职责，可放在模板方法）
  → preprocess(ctx)  → PreprocessResult   # 可多步链式
  → core(ctx, pre)   → CoreResult         # 当前：run_workflow
  → postprocess(ctx, pre, core) → PostprocessResult
  → finalize 成功/失败（任务状态 + invocation finish）
```

**阶段职责**

| 阶段 | 职责（合同审查示例） | 扩展时如何加 |
|---|---|---|
| **preprocess** | 任务 PENDING/归属/agent.type；file_parse SUCCEEDED；加载 parsed 文本与页映射；`build_workflow_input` | 新增 `TaskPreprocessStep`（如病毒扫描、配额检查、多文件合并）挂到前处理链 |
| **core** | `AgentRuntimeService.run_workflow`（或未来其它 runtime 实现） | 替换 runtime 实现或切换 blocking/streaming 收集策略；**不在此写规则判敏** |
| **postprocess** | 解析抽取 → 规则引擎 → 高亮 → 组装 `result` 与 snapshot 片段 | 新增 `TaskPostprocessStep`（如导出 PDF、通知、二次校验） |

**可插拔的最小实现约定（避免过度设计）：**

1. 平台定义阶段协议（可简化为 Protocol 方法或 `TaskPipelineStep`）：
   - `TaskPreprocessStep.run(ctx) -> PreprocessResult`
   - `TaskCoreStep.run(ctx, pre) -> CoreResult`（默认实现：`WorkflowRuntimeCoreStep`）
   - `TaskPostprocessStep.run(ctx, pre, core) -> PostprocessResult`
2. 具体 Agent 的 TaskHandler 声明**有序列表**（代码注册，本 change 不强制读 config）：
   - 合同审查：`[ReadyCheck, LoadParseContext, BuildWorkflowInput]` → `[WorkflowRuntimeCore]` → `[ParseExtraction, RuleEngine, Highlight, BuildResult]`
   - 为减少类爆炸，MVP 允许「一个阶段类内多 private 方法」，但 **preprocess / core / postprocess 三个边界方法必须在 TaskHandler 上可见且可单测**。
3. 后续若需配置化，可再映射 `agent.config_snapshot.task_pipeline`；本 change 只留扩展点与文档，不实现配置 DSL。

**失败策略**

- preprocess 失败：任务 FAILED（与现行为对齐：执行中失败 → FAILED），不调用 core。
- core 失败：FAILED + invocation FAILED，postprocess 默认不跑。
- postprocess 中**主产物**失败（规则/高亮）：任务 FAILED + invocation FAILED（与 chat lead「warning 不翻盘」不同）。
- postprocess 中**可选**步骤（未来通知类）：可 warning 记入 snapshot；本 change 合同审查无可选步骤。

### D3. 鉴权、授权与归属（强调）

```text
Client
  → Authorization: Bearer <API_KEY>
  → get_current_subject  → AuthenticatedSubject（含 api_key_id, scopes, org_unit_id）
  → ContractReviewService / TaskHandler
       · create：_assert_contract_review_scope（API Key 必须含 agent:contract_review:invoke 或 *）
       · create：校验 file_parse_task 归属
       · get/cancel/execute：校验 contract_review_task 归属
       · execute：TaskHandler 流水线（subject 只读传入，不二次解析密钥）
```

决策要点：

1. **主路径是 API Key**，不是浏览器用户 Cookie；文档与验收用例以 API Key 为准。
2. Scope 常量保持 `agent:contract_review:invoke`；`*` 视为超级 scope。
3. 任务落库继续写 `api_key_id`（及 org/user 字段），便于审计与按 Key 隔离数据。
4. TaskHandler **不得**跳过归属校验；execute 前处理或 service 层必须确认 subject 拥有该 task。
5. 本 change **不**引入「仅 internal 网络即可无鉴权」的捷径。

### D4. 注册表与工厂

```text
TaskHandlerRegistry
  factories: { AgentType.CONTRACT_REVIEW: ContractReviewTaskHandler }
  select(agent) -> 新实例
```

- 未注册 type → 明确错误，不回退 ChatHandler。
- execute：load task（含归属）→ load agent → select → `handler.execute(ctx)`。

### D5. TaskContext / 写入职责

`TaskContext`：subject、task、agent、runtime_service、db/services、request_id、阶段间 pipeline state（仅限当次实例）。

- TaskHandler 模板方法作为任务状态 + invocation 的**单一写入源**；endpoint 不组装 snapshot。
- Archi：chat = endpoint finalize；task = handler pipeline finalize。

### D6. L1–L5 落点

| 层 | 落点 |
|---|---|
| L1 | **core** 仅 `run_workflow` |
| L2 | Registry 按 type 选 TaskHandler |
| L3 | 抽取归一化在 **postprocess** |
| L4 | finalize 写 invocation 三段 snapshot |
| L5 | 规则+高亮 = **postprocess 确定性步骤** |

### D7. 模块归属

```text
modules/agent/task_handlers/
  __init__.py, pipeline.py, contract_review.py

modules/contract_review/
  service.py            # CRUD + scope/归属（原 handlers.py）
  steps/ 或现有模块      # 领域步骤
  executor.py           # 删除或薄委托
```

### D8. ChatHandler 命名

- 不强制改目录名；文档与 spec 明确 ChatHandler。

### D9. API 与 B 方案

- create/get/cancel/execute 契约不变；仅 PENDING + file_parse SUCCEEDED 可进入流水线。
- 所有上述接口均需已认证主体；API Key 调用方需具备合同审查 scope。

## Risks / Trade-offs

- [阶段拆太碎] → 三边界方法可测即可。
- [与 chat Postprocessor 两套插件] → 叙事对齐，类不强制共用。
- [双入口 executor] → 迁移后只保留 TaskHandler 流水线。
- [误把鉴权「下沉」进 core 导致难测] → 鉴权/scope 留在 endpoint 依赖 + service/preprocess，core 只做 runtime。

## Migration Plan

1. 定义 pipeline + TaskHandler 模板。  
2. 切开 `execute_task` 为三段并挂接；**迁移时原样保留 scope/归属断言**。  
3. endpoint + Registry；CRUD 重命名。  
4. ChatHandler 文档澄清。  
5. 测试含 **缺 Key / 缺 scope / 越权**；文档同步。  
6. 回滚 git revert；无 DB 迁移。

## Open Questions

- `dify_input`/`dify_output` 是否物理重命名（建议做）。  
- worker 的 `job_id` 是否进入 TaskContext（本 change 仅预留）。  
- 是否独立 `pipeline.py`（建议是）。  
- 是否在本 change 将「无 api_key_id 的主体」在 create 上直接拒绝（更严格的 API-Key-only）；**默认保持与现网一致的 scope 函数行为，仅文档强调 API Key 主路径**，除非产品明确要求收紧。

---

## 修订后的工作计划（实现顺序）

### 阶段 0 — 基线

0.1 合同审查主链路可跑。  
0.2 未提交 CR 与本 change 拆开提交。

### 阶段 1 — 命名与契约

1.1 ChatHandler 文档澄清。  
1.2 冻结 HTTP/result/鉴权契约（Bearer API Key + scope）。

### 阶段 2 — 平台流水线骨架

2.1 `pipeline.py`；2.2 TaskHandler 模板；2.3 Registry + 单测。

### 阶段 3 — 合同审查三段

3.1 领域步骤拆分；3.2 Handler 组装；3.3 注册；3.4 失败路径；**scope/归属回归**。

### 阶段 4 — 接入

4.1 endpoint → registry（仍 `get_current_subject`）；4.2 Service 重命名；4.3 去双入口。

### 阶段 5–7 — 扩展点说明、测试（含鉴权用例）、文档

### 验收清单（含鉴权）

- [ ] 无凭证 → 401  
- [ ] API Key 缺 `agent:contract_review:invoke` 且无 `*` → 创建 403  
- [ ] 越权 task → 拒绝且不调 runtime  
- [ ] 三阶段可测；core 外无 Dify client  
- [ ] API 兼容；相关测试绿  

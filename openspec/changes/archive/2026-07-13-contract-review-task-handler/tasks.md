## 1. ChatHandler 命名澄清

- [x] 1.1 更新 `modules/agent/handlers/` 包与 `ChatHandler`/`ChatHandlerRegistry` 文档字符串：明确仅服务对话流，与 TaskHandler 并列；合同审查不得注册为 Chat 回退
- [x] 1.2 核对 chat endpoint 注释用语为 ChatHandler（行为不变，无 API 变更）

## 2. TaskHandler 可插拔流水线骨架

- [x] 2.1 新增 `modules/agent/task_handlers/pipeline.py`：定义前处理 / 核心处理 / 后处理阶段协议（或等价 Protocol）与顺序执行辅助（失败短路：前处理失败不进 core，core 失败默认不进后处理主路径）
- [x] 2.2 新增 `modules/agent/task_handlers/__init__.py`：`TaskContext`（含已鉴权 `AuthenticatedSubject`）、`TaskHandler`（模板 `execute` = 状态包装 + preprocess → core → postprocess → finalize）、`TaskHandlerRegistry`（工厂、每次新实例）、`get_task_handler_registry`
- [x] 2.3 单元测试：工厂隔离、未注册拒绝、与 ChatHandlerRegistry 不串台；流水线短路（preprocess 失败不调 core）

## 3. 合同审查三段步骤落地

- [x] 3.1 将原 `execute_task` 拆为可委托的领域步骤（可放 `contract_review` 内）：前处理（就绪/归属/类型、加载 parse、组 workflow 输入）、核心（仅 `run_workflow`）、后处理（抽取归一化、规则引擎、高亮、组装 result）
- [x] 3.2 实现 `task_handlers/contract_review.py` 的 `ContractReviewTaskHandler`：组装三段步骤并实现 finalize（任务状态 + invocation 三段 snapshot）；**不**自行解析 API Key，只使用 ctx.subject
- [x] 3.3 默认注册 `AgentType.CONTRACT_REVIEW` → 该 handler 工厂
- [x] 3.4 类型不匹配 / 解析未成功 / runtime 失败 / 后处理失败路径测试；endpoint 与协议层不 import `integrations.dify.*`
- [x] 3.5 （可选）`dify_input.py`/`dify_output.py` 中性命名并更新引用

## 4. Endpoint、鉴权与 CRUD 命名

- [x] 4.1 `internal/contract_review.py` 各接口保持 `Depends(get_current_subject)`；execute 改为 `TaskHandlerRegistry.select` + `execute`，保持 HTTP 契约
- [x] 4.2 `ContractReviewHandler` → `ContractReviewService`（或等价），**保留** `agent:contract_review:invoke` / `*` 的 API Key scope 校验与任务归属校验，全仓更新引用
- [x] 4.3 删除或瘦身 `executor.py` 双入口，唯一执行实现为 TaskHandler 流水线
- [x] 4.4 回归：无凭证 401；API Key 缺 scope 创建 403；越权 get/execute 拒绝且不调 runtime；具备 scope 的 Key 可走通 create→execute

## 5. L5 与扩展点文档

- [x] 5.1 文档明确：规则+高亮 = 后处理确定性步骤；主产物失败 → 任务 FAILED（区别 chat lead warning）
- [x] 5.2 文档/注释说明如何新增前处理或后处理步骤（挂入 handler 步骤列表，不改 endpoint）
- [x] 5.3 文档明确合同审查主调用方为 **API Key**，scope 与归属模型不因 TaskHandler 重构改变

## 6. 测试

- [x] 6.1 B 方案：create 不调 runtime；PENDING 可执行；非 PENDING 拒绝；file_parse 未成功拒绝；**scope/归属/API Key**；成功 result 结构；失败落库
- [x] 6.2 流水线：可 mock core/postprocess；新增 mock 后处理步骤无需改 endpoint（结构验收）
- [x] 6.3 Chat 回归不红；execute endpoint 源码不含 `from app.integrations.dify`

## 7. 文档

- [x] 7.1 `Archi.md`：ChatHandler / TaskHandler 并列；TaskHandler = 可插拔前/核/后；§12.1 合同审查经流水线 + **API Key 鉴权**
- [x] 7.2 `PLAN-internal.md` 对应项
- [x] 7.3 `CHANGELOG.md` 摘要
- [x] 7.4 change README 引用 ADR-014；不新增 ADR

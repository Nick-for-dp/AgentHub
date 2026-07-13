# contract-review-task-handler

将合同审查对齐 **TaskHandler** 任务型调用模式（L1–L5），执行模型为 **可插拔前处理 / 核心处理 / 后处理** 流水线；对话流侧明确为 **ChatHandler**。

## 决策摘要

1. 新建 TaskHandler；原有对话流 handler 明确为 ChatHandler  
2. 保持 existing internal API  
3. 维持 B 方案（create PENDING / execute 再跑）  
4. 对齐 L1–L5  
5. 协议在 `modules/agent/task_handlers/`，业务在 `modules/contract_review/`  
6. proposal → design → specs → tasks 后再实现  
7. TaskHandler 必须步骤隔离——preprocess / core（当前=Dify workflow via AgentRuntime）/ postprocess  
8. **鉴权：合同审查主路径为 API Key（Bearer）+ scope `agent:contract_review:invoke`（或 `*`）+ 任务归属；本 change 不弱化鉴权**

决策引用：`DECISIONS.md` **ADR-014**（扩展任务型落地，不新增 ADR）。

## 实现入口

按 `tasks.md` 与 `design.md`「修订后的工作计划」执行；或请助手 apply change。

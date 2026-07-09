# agent-runtime-handler-dispatch

按 agent.type 分发对话流处理器；剔除 chat endpoint 对 Dify 专有类型的依赖；线索收集抽为可插拔后处理器。

决策引用：`DECISIONS.md` **ADR-014**（Agent runtime 抽象与多类型 Agent 支撑）。本 change 为 ADR-014 后半段落地，不新增 ADR。

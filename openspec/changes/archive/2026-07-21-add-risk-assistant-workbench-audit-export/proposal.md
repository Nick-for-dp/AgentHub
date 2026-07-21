## Why

风控助手已经具备多文件抽取、确定性核对、LangGraph 暂停恢复和人工复核 API，但内部用户仍缺少可正式演示和持续使用的 Web 工作台，也无法导出业务要求的审计底稿“业务总览”。现在需要完成 `PLAN-internal.md` I7 第 6 项和第 7 项中的非 ERP 部分，并让页面、API 与导出契约能够直接延续到正式上线，后续原则上只替换或扩展 LangGraph 内部工作流。

本 change 引用 ADR-015、ADR-017、ADR-018、ADR-019，继续遵守 internal profile 隔离、Cookie Session、AgentHub 后端确定性判断和单一 LangGraph 人工复核边界。

## What Changes

- 新增 internal 风控助手工作台，支持多文件选择、文档类型声明、预签名上传、解析、创建任务、执行、轮询、取消、失败恢复和页面刷新后的任务找回。
- 新增当前用户风控任务分页列表和稳定任务详情入口；列表只返回轻量摘要，详情继续使用既有 task read、`result`、`review_context` 和 `review_events` 契约。
- 新增业务总览投影，将 canonical result 的原子审计字段确定性映射为审计底稿第一个 sheet 的 17 个业务项目；工作台和 Excel 导出复用同一投影，不各自维护映射规则。
- 工作台展示完整业务总览、通用 checks、warnings、来源文件原始名称、页码、quote、bbox、候选值和人工复核历史；只有当前 review item 可修改。
- 新增有权限的原始来源文件打开或下载能力，前端不直接使用对象存储 SDK；一期不承诺 OCR bbox 在原页上的精确框选。
- 新增 Excel 导出接口，只生成一个名为“业务总览”的可见 sheet，复刻参考审计底稿第一个 sheet 的标题、业务编号、编制日期、项目、内容和来源文件结构；不生成隐藏元数据或其它审计 sheet。
- 来源文件列使用持久化的原始文件名；人工复核后的字段追加人工复核标识，但修改前后值、理由和操作人仍以系统 review event 为权威事实。
- 泛化 internal 前端布局和导航，使合同审查与风控助手均有稳定入口，同时保持 external profile 不注册风控路由和资源。
- 保持前端与导出只依赖稳定的 `audit_items/checks/warnings/review_items` 和业务总览投影，不硬编码当前 LangGraph 节点拓扑或 ERP 专有列。

Non-goals：

- 不接入 ERP，不新增 ERP snapshot、ERP facts 或文档与 ERP comparison。
- 不在采购合同数量与销售合同数量之间建立风险核对规则；二者只是合同约定事实，ERP 接入前只展示。
- 不重写当前演示版 LangGraph，不建设通用 graph 插件注册框架，也不承诺演示数据/checkpoint 的生产兼容。
- 不定义业务模式枚举或别名映射；业务模式只依据审批样表“业务性质”栏的勾选项生成可读原文表达，不读取“业务模式简介”长文本。
- 不生成“单据清单、数量核对、金额核对、资金流向、差异汇总、数据溯源”等其它 sheet。

## Capabilities

### New Capabilities

- `risk-assistant-review-workbench`: internal 风控任务提交、找回、状态展示、完整审计信息、证据和人工复核工作台。
- `risk-audit-workbook-export`: canonical result 到单 sheet“业务总览”Excel 的版本化投影和下载。

### Modified Capabilities

- `risk-assistant-task-execution`: 增加当前 Cookie 用户可分页查询其风控任务摘要的要求，并取消业务模式处理必须预建通用 enrichment 注册点的约束；后续 ERP 直接演进 LangGraph。
- `risk-document-fact-extraction`: 收紧审批样表业务模式来源，只允许读取“业务性质”栏并排除“业务模式简介”。

## Impact

- 后端扩展 `modules/risk_assessment/` 的列表 service/schema、业务总览 projector、来源文件访问和 Excel export service，并新增 internal endpoint。
- 后端增加 Excel 模板处理依赖和一个脱敏、无历史业务数据的版本化“业务总览”模板。
- 前端新增风控助手 API client、集中状态 composable、页面和拆分组件；调整 internal layout、路由和默认导航文案。
- 不新增数据库表；沿用 `risk_assessment_task`、`risk_assessment_document`、`risk_review_event`、`file_parse_task` 和既有权限归属。
- 后续 ERP change 只负责 integration adapter、snapshot、LangGraph 节点和 checks/result enrichment，不重新建设本 change 的页面、上传、复核和 Excel 基础链路。

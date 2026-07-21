## Why

面向用户的工作台、复核和审计底稿导出由 `add-risk-assistant-workbench-audit-export` 建成稳定产品边界，但正式上线前仍必须接入 ERP 独立事实并完成数量、金额等业务核对。本 change 承接原 `add-risk-erp-workbench-export` 的 ERP 部分，完成 `PLAN-internal.md` I7 第 7 项剩余的 ERP 对账，不再重复建设前端或 Excel。

本 change 引用 ADR-015、ADR-018、ADR-019：ERP 只由 internal 后端访问，文档事实与 ERP 事实独立，确定性核对属于 AgentHub，正式图继续使用单一 LangGraph 承载自动路径和人工复核。

## What Changes

- 新增 internal-only ERP integration adapter、配置、认证、超时、有界重试和响应 schema 校验；领域代码不依赖 ERP 厂商 SDK 或认证细节。
- 新增不可变 ERP 查询快照，保存查询键、接口/schema 版本、时间、状态、脱敏响应或对象存储 URI 与 hash，后续 ERP 更新不得改写历史任务证据。
- 将 ERP 响应归一化为稳定 ERP facts；合同文档事实、ERP facts 和人工最终值保持独立，ERP 不得自动覆盖文档值或替 UNCERTAIN 字段选择候选。
- 直接将 ERP 查询、归一化和 comparison 节点接入正式 LangGraph，升级 graph/schema/rule 版本；不为演示版 graph 建设通用插件注册框架，也不兼容演示 checkpoint。
- 将 ERP 核对输出为工作台已经支持的通用 checks/evidence 契约，状态至少覆盖 MATCHED、MISMATCH、ERP_MISSING、DOCUMENT_MISSING、ERP_UNAVAILABLE、NOT_COMPARABLE。
- ERP 不可用时不得伪造匹配；是否进入人工复核由关键字段和正式任务策略决定。
- 扩展 task result 和 invocation snapshot 的 ERP 版本/快照引用，但保持工作台上传、任务详情、人工复核和单 sheet Excel 接口不变。

Non-goals：

- 不新增或重写风控 Web 工作台、任务列表、来源文件访问、业务总览 projector 和 Excel writer。
- 不改变审计底稿只导出第一个“业务总览”sheet 的范围。
- 不让 ERP 成为自动纠正文档抽取的真值源，不建设通用 ERP 同步平台。
- 不兼容或迁移上线前演示任务/checkpoint；正式联调前可以清理并重新创建演示数据。
- 不建设通用 LangGraph plugin/registry 平台，不扩展业务模式枚举。

## Capabilities

### New Capabilities

- `risk-erp-reconciliation`: ERP adapter、不可变快照、ERP facts 和版本化确定性核对。

### Modified Capabilities


## Impact

- 新增 `backend/app/integrations/erp/`、ERP 配置、snapshot model/repository/service 和 Alembic migration。
- 扩展 `modules/risk_assessment/graph/`、state/result schema 和规则测试，正式图版本与演示图结果明确区分。
- 后续生产部署增加 ERP URL、credential reference、timeout/retry 和启用开关；external profile 不初始化或注册 ERP 能力。
- `add-risk-assistant-workbench-audit-export` 的页面、API、业务总览和 Excel 不需要重新实现，只消费新增通用 checks/evidence。

## Context

`add-risk-assistant-workbench-audit-export` 将提交、任务列表、完整复核、通用 checks/evidence、来源访问和单 sheet Excel 建成稳定用户边界。当前 document-only LangGraph 只用于上线前演示和业务确认；正式上线必须查询 ERP 独立事实并核对合同数量、金额等指标，演示任务和 checkpoint 不要求迁移。

本 change 跨 integration、数据库、领域 service 和 LangGraph：

- `integrations/erp/` 只封装 ERP 协议、认证和响应校验。
- `modules/risk_assessment/erp/` 负责快照、归一化、字段映射和 comparison 规则。
- repository 只读写 `risk_erp_snapshot`；service 负责权限、脱敏和编排。
- graph node 只依赖标准 ERP port 和领域 schema，不构造厂商 HTTP 请求。
- 前端继续消费既有通用 checks/evidence，不直接访问 ERP。

ERP 接口地址、认证、查询键、字段编码、容差和 SLA 尚需 ERP/业务团队确认，因此实现顺序先冻结接口契约和 fake client，再接真实测试环境。

## Goals / Non-Goals

**Goals:**

- 通过可替换 adapter 安全访问 ERP，并保存可追溯的不可变查询快照。
- 将 ERP facts 与文档事实独立保存，使用版本化确定性规则产生通用 checks。
- 正式 LangGraph 在人工复核前完成 ERP 查询和核对，ERP 不可用时 fail safe。
- 保持现有工作台、复核 API、业务总览 projector 和单 sheet Excel 用户契约不变。

**Non-Goals:**

- 不建设 ERP 通用同步平台、主数据平台或前端 ERP 专用工作台。
- 不让 ERP 覆盖文档值或替 UNCERTAIN 字段选择候选。
- 不比较采购合同数量与销售合同数量；分别和对应 ERP 采购/收货、销售/发货事实核对。
- 不兼容演示版 graph checkpoint，不建设通用 LangGraph 插件注册框架。
- 不修改 Excel sheet 范围和业务模式原文策略。

## Decisions

### 1. ERP 通过标准 port 访问

定义最小对象：

```text
ErpRiskQuery
  business_code
  purchase_contract_number?
  sales_contract_number?

ErpRiskQueryResult
  status
  schema_version
  queried_at
  payload
  error_code?
```

`ErpRiskDataClient` Protocol 只暴露 query；factory 按 internal 配置选择 disabled/fake/real。认证、HTTP timeout、有限 retry、429/backoff 和厂商响应 schema 只存在于 `integrations/erp`。graph/service 不读取 token，也不依赖厂商 SDK。

生产启用 ERP 时配置缺失必须启动失败；external profile 和未授权 Agent 不初始化真实 client。选择 adapter 而不是在 graph node 内直接发 HTTP，是为了便于 fake 回归、厂商切换和日志脱敏。

### 2. 每次查询保存不可变 snapshot

新增 `risk_erp_snapshot`：

```text
id/task_id
business_key
interface_version/schema_version
status
payload_json | payload_uri
payload_hash
queried_at
error_code/error_message
created_at
```

每次查询只 insert，不 update 历史 payload。响应先按契约脱敏，再生成稳定 JSON hash；超过阈值转 internal MinIO，表内保存 URI 和 hash。snapshot 是该次审计证据，ERP 后续修改不影响历史任务。数据库变化通过 Alembic migration 创建 task/time/status 索引。

### 3. ERP facts 与文档 facts 双轨保存

ERP mapper 输出命名空间明确的标准 facts，例如主体编码/名称、采购/销售合同号、商品、采购/销售数量、单价、金额和日期，并记录 ERP field code、value、unit、snapshot id 和 warnings。

task result 可增加 `erp_facts` 和 `erp_snapshot_summary`，但现有 `document_facts`、`audit_items` 和人工最终值保持不变。ERP 不写入 `BusinessOverviewProjection` 的文档内容，也不改变 Excel 17 行的来源事实；核对只通过 checks/evidence 表达。

### 4. comparison 复用工作台通用 checks 契约

ERP comparison 领域对象在图内归一化为：

```text
rule_code/version/outcome/message
affected_fields
input_evidence[]
  side             DOCUMENT | ERP
  field_code
  value/unit
  sources | snapshot_id
difference?
tolerance?
```

outcome 至少包含 MATCHED、MISMATCH、ERP_MISSING、DOCUMENT_MISSING、ERP_UNAVAILABLE、NOT_COMPARABLE，可按业务确认增加 MATCHED_WITHIN_TOLERANCE。现有工作台按通用 check/evidence 展开，不增加固定 ERP 列。

数量核对轴固定为合同对 ERP：采购合同数量只与 ERP 采购/收货事实核对，销售合同数量只与 ERP 销售/发货事实核对。采购合同数量和销售合同数量之间不生成 comparison。

### 5. 正式 graph 直接替换演示拓扑

正式数据流：

```text
load/extract/type validate
 -> normalize document facts
 -> run document checks
 -> build ERP query key
 -> fetch and persist ERP snapshot
 -> normalize ERP facts
 -> run ERP comparisons
 -> build review items
 -> materialize result
 -> review route / finalize
```

直接修改 builder 和 state，不增加 extension registry。发布时升级 graph/schema/rule version；上线前演示数据和 WAITING_REVIEW checkpoint 可清理并重新创建。正式图仍使用 ADR-019 的单 thread、同 invocation、interrupt/review/resume 机制。

人工修改文档字段后，恢复路径必须重跑所有受影响的 document checks 和 ERP comparisons，但不得重新查询 ERP；继续引用同一 snapshot。只有用户显式重新执行新的任务才产生新 snapshot。

### 6. ERP 不可用时 fail safe

认证失败、超时、响应 schema 错误和字段缺失必须转换为稳定 error/check，不泄露响应或 credential。系统不得把无法查询显示成 MATCHED。正式任务策略由关键字段配置决定：关键 ERP 事实不可用时进入 WAITING_REVIEW；非关键字段可 warning 后完成。

feature flag 只用于联调和回滚，正式验收要求真实 adapter 开启。关闭时明确输出 ERP_DISABLED/NOT_COMPARABLE，不伪装生产核对已完成。

## Risks / Trade-offs

- [ERP 接口口径晚确认] → 先冻结 `erp-contract-v1.md` 和 fake fixtures，真实 adapter 只在契约签字后实现。
- [ERP 被误当作文档纠错真值] → 双轨字段、snapshot 来源和 comparison-only 写入，禁止覆盖 document facts。
- [快照含敏感字段] → 白名单保留、字段级脱敏、hash 和日志测试；大 payload 转 internal MinIO。
- [ERP 暂时不可用阻塞业务] → 有界 retry、稳定 ERP_UNAVAILABLE 和关键字段策略，人工只能确认处置，不能伪造 ERP 值。
- [演示 checkpoint 在正式图不可恢复] → 上线前清理/完成演示任务并明确版本升级；无生产兼容承诺。
- [工作台无法显示新规则细节] → comparison 必须遵守既有通用 check/evidence schema，端到端契约测试用当前工作台 DTO 验证。

## Migration Plan

1. ERP/业务团队确认 `erp-contract-v1.md`，使用 fake client 完成 mapper、snapshot 和 comparison 回归。
2. 执行 Alembic migration，新表上线但 feature flag 保持关闭。
3. 接入 ERP 测试环境，完成认证、超时、限流、字段缺失和脱敏验收。
4. 清理或完成演示 WAITING_REVIEW 任务，升级正式 graph/schema/rule 版本并启用 ERP 节点。
5. 用工作台完成合同→ERP check→人工复核→Excel 的生产前验收，确认页面/API/Excel 无需重建。

回滚时关闭 ERP graph 启用开关并回退应用版本；snapshot 表保留审计记录，不回写或删除历史任务。数据库 downgrade 只用于非生产验证。

## Open Questions

- ERP 查询键、认证协议、字段编码、单位、容差、测试环境和 SLA。
- 哪些 ERP comparison 属于关键项并必须进入 WAITING_REVIEW。
- 收货/发货、订单/结算存在多条记录时的聚合口径和截止时点。

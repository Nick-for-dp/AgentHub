## Context

第一、二阶段已经形成 document-only 风控任务：多文件通过 `file_parse_task` 和原始文件名关联到 `risk_assessment_task`，`RiskAssessmentTaskHandler` 执行单一 LangGraph，结果通过 `result_snapshot` 保存 `audit_items/document_facts/checks/warnings/review_items`，关键项可进入 `WAITING_REVIEW` 并从 MySQL checkpoint 恢复。现有 internal API 已支持 create/get/execute/reviews/cancel，但前端只有合同审查辅助页，风控助手没有正式入口；业务也只能阅读 JSON/报告，不能获得审计底稿第一个 sheet。

当前 LangGraph 是上线前用于和用户确认抽取、规则和复核口径的演示版本。ERP 接口必须在正式上线前接入，但演示任务和 checkpoint 不要求生产兼容。因此本 change 要把上传、任务管理、页面、复核、证据和 Excel 建成稳定产品边界，同时避免把当前 graph 节点顺序、document-only 假设或 ERP 专用展示焊死在前端和导出层。

模块边界：

- endpoint：`api/v1/endpoints/internal/risk_assistant.py` 只处理 Cookie 鉴权、参数和响应。
- service/repository：`modules/risk_assessment/` 负责归属、分页、投影、导出和来源文件授权。
- integration：预签名下载继续只通过 `integrations/object_storage.FileStorage`；业务层不直接调用 MinIO SDK。
- frontend：只调用 AgentHub internal API，不直接调用 LangGraph、PaddleOCR、Qwen 或对象存储 SDK。

本 change 不新增数据库结构，不需要 Alembic migration。

## Goals / Non-Goals

**Goals:**

- 交付内部用户可正式演示的风控工作台，完成上传、执行、复核、结果查看和任务找回闭环。
- 建立 graph-independent 的业务总览和 checks 展示契约，使 ERP 上线时原则上只演进 LangGraph 和后端集成。
- 用同一个业务总览 projector 支撑 Web 和 Excel，避免字段、来源和状态规则漂移。
- 只导出审计底稿第一个“业务总览”sheet，且不携带样例历史数据、隐藏 sheet 或其它未生成审计内容。
- 保留真实原始文件名、证据和人工决定的系统级审计追踪。

**Non-Goals:**

- 不接入 ERP，不定义 ERP 查询键、snapshot、facts、comparison 或容差。
- 不修改当前 LangGraph 拓扑，不建设通用 graph 插件系统，不兼容演示 checkpoint 到生产图。
- 不比较采购合同数量与销售合同数量；ERP 接入前仅展示两份合同各自约定。
- 不增加业务模式枚举、其它审计 sheet、部门代办或 API Key 风控入口。
- 不承诺扫描 PDF bbox 的页面像素级高亮。

## Decisions

### 1. Web 和 Excel 共用极简业务总览投影

新增纯确定性 `BusinessOverviewProjector`，输入现有 canonical result 和 review events，输出：

```text
BusinessOverviewProjection
  business_code
  generated_at
  rows[]
    code
    label
    content
    status          READY | PARTIAL | MISSING | NEEDS_REVIEW
    source_files[]  原始文件名去重列表
    field_codes[]   对应 canonical 字段
    is_human_reviewed
```

投影只生成展示数据，不写回 task result，不把 ERP 当作字段真值，也不替代 `review_context`。复核提交仍使用既有 review item、target code 和 checkpoint version；前端不得提交投影行作为新的领域对象。

17 行映射固定为：

| 业务总览项目 | canonical 字段/组合 |
|---|---|
| 业务模式 | `raw_business_mode_text`（仅来自审批样表“业务性质”栏） |
| 上游供应商 | `upstream_supplier` |
| 下游客户 | `downstream_customer` |
| 货物名称 | `goods_name` |
| 采购合同号 | `purchase_contract_number` |
| 销售合同号 | `sales_contract_number` |
| 采购合同签订日 | `purchase_signing_date` |
| 销售合同签订日 | `sales_signing_date` |
| 交货地点 | `delivery_location` |
| 采购含税单价 | `purchase_unit_price_tax_included` |
| 销售含税单价 | `sales_unit_price_tax_included` |
| 合同约定数量 | `purchase_quantity + sales_quantity` |
| 采购合同含税金额 | `purchase_amount_tax_included` |
| 销售合同含税金额 | `sales_amount_tax_included` |
| 大客户优惠 | `key_customer_discount` |
| 保证金比例 | `deposit_ratio + deposit_amount`；金额未明示时由 `purchase_amount_tax_included × deposit_ratio` 确定性生成 |
| 浮动费 | `floating_fee + occupied_days` |

金额、单价、数量、比例、日期和天数由 projector 统一格式化。`key_customer_discount` 按合同明确写出的优惠金额处理，单位修正为 `CNY`，不再按 `CNY/TON` 展示。

合同数量规则不是核对规则：两侧相同时合并显示并保留两份来源；不同时中性显示“采购约定：X；销售约定：Y”，不产生 warning、review item 或失败结论。

业务模式不读取“业务模式简介”长文本，只读取审批样表“业务性质”栏的已勾选项，并按参考底稿形成可读表达。例如样表同时勾选“预付款”和“其他（联销等）：联销”时，输出“联销（预付款+联合销售）”。这不是业务模式枚举或别名表，不从采购/销售合同推断。

当采购合同未明示保证金金额，但 `purchase_amount_tax_included` 和 `deposit_ratio` 均为可用值时，`DEPOSIT_RATIO_AMOUNT` 规则 SHALL 按“采购合同含税金额 × 保证金比例 ÷ 100”生成 `deposit_amount`，保留两个输入字段的来源并标记 derivation rule。若合同已经明示保证金金额，则规则只核对一致性，不覆盖原文值。

由于该规则改变了 canonical fact 的生成语义，`RULE_SET_VERSION` 从 `risk-rules-v1` 升级为 `risk-rules-v2`，历史演示结果仍可区分。

选择该方案而不是让前端直接拼 17 行，是为了让 Excel、桌面和窄屏展示使用同一业务口径，并使未来 graph 变化不要求前端理解新的事实选择过程。

### 2. 任务列表使用轻量分页 DTO，详情保持既有契约

新增：

```text
GET /internal/risk-assistant/tasks?page=1&page_size=20&status=...
```

返回 `RiskAssessmentTaskSummaryRead` 分页列表，只包含 id、business_code、status、current_node、document_count、created_at、updated_at、finished_at 和 error summary，不返回 result/review_context。当前规模小于 50 人，普通 offset pagination 足够；后续数据量增长再改 cursor，不提前增加游标对象。

列表严格限定当前 Cookie 用户拥有的任务，沿用既有 creator-first 归属规则，不扩展同部门代办。详情继续通过 `GET /tasks/{id}` 获取。前端路由使用 `/internal/risk-assistant` 和 `/internal/risk-assistant/tasks/:taskId`；刷新详情页后按 task 状态恢复轮询、复核或结果展示。

### 3. 工作台状态机与 LangGraph 节点解耦

每个上传文件独立经历：

```text
SELECTED -> PREPARING_UPLOAD -> UPLOADING -> PARSING -> READY | FAILED
```

风控任务只按稳定业务状态展示：

```text
PENDING -> RUNNING -> WAITING_REVIEW -> RUNNING ... -> SUCCEEDED | FAILED | CANCELLED
```

页面不使用硬编码 graph node 列表驱动步骤条；`current_node` 只用于详情诊断，未知节点统一显示“处理中”。execute/review 请求响应不确定时先 GET task，再决定轮询或允许重试，复用合同审查 composable 的 AbortController、run id 和指数退避模式。

工作台使用集中 `useRiskAssistantWorkbench` 管理请求和轮询，页面组件不得散落多个互相矛盾的 loading 布尔值。

### 4. 工作台以业务总览为主视图，完整审计上下文为复核依据

桌面布局采用最近任务区域和主工作区；无 task 时显示多文件提交，选择 task 后显示：

1. 业务编号、任务状态、耗时和主要操作。
2. 17 行业务总览表。
3. 通用 checks/warnings 区，展示 code、outcome、message、affected fields 和 input evidence。
4. `WAITING_REVIEW` 时的复核面板，展示当前候选、来源、动作和必填原因。
5. 证据抽屉及 review event 时间线。

页面仍可展开 `review_context.audit_items` 查看全部原子字段，满足复核时展示 FOUND/MISSING/UNCERTAIN 全量信息的主规格。业务总览不是对原子审计信息的删减，只是用户主视图。

未来 ERP 图继续把确定性核对写入通用 `checks` 和 evidence 结构；当前 UI 不预建“文档事实/ERP事实/comparison”固定三列，也不显示虚假的 ERP 匹配状态。

### 5. 证据先保证真实可访问，不伪造位置高亮

前端直接展示 source 中已有的 original filename、declared type、page、quote、block id 和 bbox。点击证据时可按权限请求：

```text
GET /internal/risk-assistant/tasks/{task_id}/documents/{document_id}/access
```

service 校验 task/document/file_parse 归属后，通过 `FileStorage.create_presigned_download_url` 返回短期下载地址和过期时间。前端只打开该地址，不持有对象存储凭证或使用 SDK。

扫描 PDF 的 PaddleOCR bbox 坐标不等同于浏览器 PDF 坐标；一期只跳转/提示页码并展示 quote、bbox 文本。无法定位时显示 warning，不绘制近似框。DOCX 也以原文件下载和解析 block 文本为主，不另建 Office 在线预览服务。

### 6. Excel 由代码生成单一“业务总览”sheet

后端使用 `openpyxl` 从空 workbook 确定性生成模板版本 `risk-business-overview-v1`，不复制带历史数据的真实样例文件。布局固定为：

```text
A1:C1  供应链业务核对审计底稿
A2:C2  业务编号 + 编制日期
A4:C4  一、业务基本信息
A5:C5  项目 | 内容 | 来源文件
A6:C22 17 个业务总览项目
```

只保留一个可见 sheet，名称必须为“业务总览”；不得创建隐藏 metadata 或其它 sheet。样式显式定义微软雅黑、深蓝表头、白字、边框、对齐、列宽和换行。用户可见内容只来自 `BusinessOverviewProjection` 和业务编号/导出日期。

导出接口：

```text
GET /internal/risk-assistant/tasks/{task_id}/export?template_version=risk-business-overview-v1
```

只允许任务拥有者导出 SUCCEEDED task；文件名使用清洗后的 `供应链业务核对审计底稿_{business_code}.xlsx`。人工复核最终值正常写入内容列，来源文件列在真实原始文件名后追加“人工复核”；详细修改历史仍由系统 task/review event 查询，不写入 Excel。

### 7. internal 布局泛化但不改变部署 profile 决策

`InternalLayout.vue` 的品牌改为通用 AgentHub 内部智能体，增加“合同审查”和“风控助手”导航；现有 internal 默认首页保持兼容，不强制改变合同审查用户入口。风控路由只在 internal build 注册，external profile 的路由测试必须断言入口和懒加载组件均不存在。

## Risks / Trade-offs

- [业务性质栏包含复选框和自由填写内容] → 抽取提示明确只选择已勾选项，并用真实审批样表回归；不读取相邻“业务模式简介”。
- [扫描件没有可靠浏览器坐标] → 展示页码/quote/bbox 和原件访问，不做误导性高亮。
- [同步 execute 耗时导致浏览器超时] → 响应不确定时先查询 task，随后轮询；不重复执行。
- [Web 与 Excel 映射漂移] → 两者必须调用同一个 projector，映射和格式化只保留一份测试基线。
- [Excel 文件脱离系统后缺少完整技术版本] → 业务编号和编制日期用于定位；技术版本、人工理由和操作人继续由 task/review event 作为权威事实，不扩大用户可见 sheet。
- [未来 ERP 结果需要新展示] → ERP 核对遵循通用 checks/evidence 契约；只有业务明确要求新的独立页面语义时才另开前端 change。

## Migration Plan

1. 增加 projector、任务列表、来源访问和 Excel service/API，保持现有详情/执行/复核接口不变。
2. 新增前端 API client、composable、路由和工作台组件，泛化 internal 导航。
3. 使用四文件真实样本完成 document-only 用户演示、人工复核和 Excel 对照验收。
4. 正式上线前由后续 ERP change 直接演进现有 LangGraph 和 checks 产出；演示任务/checkpoint 可清理或重新执行，仅版本号用于区分结果。

回滚不涉及数据库：移除风控工作台路由和新增 endpoint 即可，现有 create/get/execute/reviews/cancel 与历史任务不受影响。

## Open Questions

本 change 的产品边界已确认：Excel 只包含第一个“业务总览”sheet；任务只对创建者可见；采购/销售合同数量不互相核对；ERP 和正式 graph 由后续 change 在上线前接入。

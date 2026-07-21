## 1. 业务总览投影

- [x] 1.1 在 `modules/risk_assessment/overview/schemas.py` 定义 `BusinessOverviewProjection`、`BusinessOverviewRow` 和稳定 display status；添加 schema 序列化测试
- [x] 1.2 在 `overview/catalog.py` 固定 17 个项目顺序、label 和 canonical field_codes，测试项目数量、顺序和编码唯一性
- [x] 1.3 在 `overview/projector.py` 实现 14 个直接字段的值格式化和 MISSING/NEEDS_REVIEW 状态映射，覆盖文本、日期、数量、单价、金额和比例测试
- [x] 1.4 在 projector 中实现合同约定数量组合：相同值合并、不同值中性分列、单侧缺失标记 PARTIAL；断言不产生风险判断或修改 canonical checks
- [x] 1.5 在 projector 中实现保证金比例/金额和浮动费/占用天数组合，测试未明示项不得由其它字段计算
- [x] 1.6 修正 `key_customer_discount` 的 audit catalog/单位推断为 CNY，并增加 normalization 回归测试，防止再次显示为 CNY/TON
- [x] 1.7 实现 source_files 去重、原始文件名保留和 HUMAN_REVIEW 标识；测试非标准文件名及人工修正前后工作台投影一致
- [x] 1.8 新建样例 projection fixture，按真实审计底稿 17 项逐行断言内容和来源，不在 fixture 中保存密钥、provider 响应或对象 URL

## 2. 任务列表与来源文件授权

- [x] 2.1 在 `risk_assessment/schemas.py` 增加 `RiskAssessmentTaskSummaryRead` 和分页响应 schema，明确列表不含 result/review_context/review_events
- [x] 2.2 扩展 repository 的 task 查询为带 page/page_size/status 和 count 的 creator-first 分页，测试排序、边界页和状态筛选
- [x] 2.3 在 service 中实现当前 Cookie 用户列表权限和摘要装配，测试同部门其它创建者任务不可见、API Key 主体被拒绝
- [x] 2.4 新增 `GET /internal/risk-assistant/tasks` endpoint 和参数校验，测试 20 条默认分页、非法 page_size、external profile 不注册
- [x] 2.5 定义来源文件访问响应 schema，并在 service 中按 task→document→file_parse 校验归属后调用 `FileStorage.create_presigned_download_url`
- [x] 2.6 新增 `GET /tasks/{task_id}/documents/{document_id}/access` endpoint，测试合法短期 URL、跨任务 document、越权任务和不存在文件均 fail closed
- [x] 2.7 增加来源访问日志脱敏测试，断言签名 query、对象存储 credential 和 source_uri 不进入日志或错误响应

## 3. 单 sheet 审计底稿导出

- [x] 3.1 在 `backend/pyproject.toml` 增加锁定版本的 `openpyxl` 并更新 `uv.lock`，验证 external profile 启动不触发风控 export 初始化
- [x] 3.2 在 `risk_assessment/export/layout.py` 定义 `risk-business-overview-v1` 的 A1:C22 单元格、合并区、列宽、行高、字体、颜色、边框和对齐常量
- [x] 3.3 在 `export/writer.py` 从空 workbook 生成唯一“业务总览”sheet，测试不存在默认 Sheet、隐藏 sheet、其它审计 sheet 和样例历史值
- [x] 3.4 在 writer 中填充标题、业务编号、北京时间编制日期、17 行 projection 内容和来源，验证 sheet 名、A1:C22、合并区域及关键样式
- [x] 3.5 在 `export/service.py` 实现 SUCCEEDED/归属/template_version 校验、projector 调用、文件名清洗和内存流输出，不重新 OCR、execute 或写 task result
- [x] 3.6 新增 `GET /tasks/{task_id}/export` endpoint，设置正确 MIME type、Content-Disposition 和异常响应
- [x] 3.7 新建 workbook 内容回归测试，覆盖正常值、MISSING、PARTIAL、NEEDS_REVIEW 防御分支、HUMAN_REVIEW 来源和非标准原始文件名
- [x] 3.8 新建导出权限/状态测试，覆盖 WAITING_REVIEW、FAILED、CANCELLED、越权用户和未知模板版本均不生成文件
- [x] 3.9 用 openpyxl 重新读取真实样例任务导出物，逐行对照参考底稿第一个 sheet，并断言 workbook 只有一个可见 sheet

## 4. 前端 API、路由与 internal 导航

- [x] 4.1 将预签名上传和 file parse 公共类型/函数从合同审查 client 收敛到 `frontend/src/api/internalFiles.ts`，保持合同审查现有行为和测试通过
- [x] 4.2 新建 `frontend/src/api/internalRiskAssistant.ts`，定义任务摘要/详情、projection、audit item、check、review event、document access 和导出类型
- [x] 4.3 在 risk client 中实现 list/create/get/execute/review/cancel/access/export，请求错误统一转换为安全中文信息
- [x] 4.4 为 risk client 添加 mock axios 测试，覆盖分页参数、checkpoint header/payload、Blob 下载、409 和 403 错误归一化
- [x] 4.5 在 `router/routes.ts` 注册 `/internal/risk-assistant` 与 `/internal/risk-assistant/tasks/:taskId`，复用同一工作台页面并保持 requiresAuth
- [x] 4.6 泛化 `InternalLayout.vue` 品牌和导航，增加合同审查/风控助手入口并保持现有默认首页兼容
- [x] 4.7 扩展 deployment profile/router 测试，断言 external 构建不存在风控路由、导航配置和页面入口

## 5. 风控工作台集中状态机

- [x] 5.1 新建 `useRiskAssistantWorkbench.ts` 的文件包、任务列表、选中任务、轮询和错误状态，禁止页面组件自行维护重复 loading 状态
- [x] 5.2 实现文件校验、类型声明、预签名上传、独立进度、parse 创建/轮询和单文件失败重试
- [x] 5.3 实现 business_code 校验、risk task 创建、execute 和终态轮询；execute 不确定时先 GET 并只对确认 PENDING 的任务允许安全重试
- [x] 5.4 实现任务列表分页/状态筛选、route taskId 加载和页面刷新恢复；RUNNING 自动轮询、WAITING_REVIEW 停止普通终态等待
- [x] 5.5 实现 review 提交、checkpoint 409 后刷新、同 task 恢复轮询和重复提交防护
- [x] 5.6 实现 cancel、source access、Excel Blob 下载及组件卸载时 AbortController/XHR 清理
- [x] 5.7 为 composable 添加顺序测试：四文件成功链路、单文件失败重试、旧 run 晚返回不得污染新状态
- [x] 5.8 为 composable 添加恢复测试：刷新 RUNNING、刷新 WAITING_REVIEW、execute 超时先 GET、review 409 刷新、终态不继续轮询

## 6. 工作台页面和组件

- [x] 6.1 新建 `RiskAssistantPage.vue` 页面壳，接入 route taskId、最近任务区、空状态、新建任务和详情工作区
- [x] 6.2 新建 `RiskFilePackagePanel.vue`，实现多文件选择、声明类型、业务编号、进度、移除和单文件重试；预签名 XHR 必须 `withCredentials=false`
- [x] 6.3 新建 `RiskTaskHeader.vue`，展示业务编号、稳定任务状态、耗时、错误和取消/刷新操作；未知 current_node 显示“处理中”
- [x] 6.4 新建 `RiskOverviewTable.vue`，按 projector 17 行展示 content、状态、原始来源文件，并支持打开相关原子审计信息
- [x] 6.5 新建 `RiskChecksPanel.vue`，通用展示 code/outcome/message/affected_fields/input_evidence，ERP 未接入时不渲染虚假匹配列
- [x] 6.6 新建 `RiskReviewPanel.vue`，按 FIELD/DOCUMENT_TYPE 渲染允许动作、候选值、修正值和必填原因，只允许提交当前 active review item
- [x] 6.7 新建 `RiskEvidenceDrawer.vue`，展示文件名、声明类型、页码、quote、block id、bbox、warnings 和短期原文件打开入口，不绘制未经证明的 bbox 高亮
- [x] 6.8 新建 `RiskReviewTimeline.vue`，只读展示修改前后值、原因、操作人和时间；不允许从历史事件重新提交
- [x] 6.9 在 SUCCEEDED 详情增加 Excel 导出按钮、下载进度和错误提示，其它状态禁用并说明原因

## 7. 组件测试与响应式验收

- [x] 7.1 为任务列表和 route 恢复添加组件测试，覆盖 loading、empty、error、分页、状态筛选和刷新后选中任务
- [x] 7.2 为业务总览/checks/evidence 组件添加测试，覆盖长业务模式、非标准文件名、MISSING/PARTIAL/HUMAN_REVIEW 和无精确坐标 warning
- [x] 7.3 为 review 组件添加测试，覆盖候选选择、人工修正、确认缺失、原因必填、重复提交禁用和 checkpoint 冲突提示
- [x] 7.4 完成 1366px 双区工作台布局，按 UI checklist 检查业务总览、复核面板、抽屉和主要操作无横向溢出
- [x] 7.5 完成 1024px 与 375px 的任务列表收拢、纵向/标签页布局，确保原因输入、提交和导出按钮不被遮挡
- [x] 7.6 启动 internal 前端并用浏览器完成 idle、RUNNING、WAITING_REVIEW、SUCCEEDED、FAILED 五组截图验收

## 8. 集成回归与文档收口

- [x] 8.1 新增后端端到端测试：四文件 parse 结果→创建→execute→WAITING_REVIEW→人工恢复→SUCCEEDED→Excel 导出
- [x] 8.2 在端到端测试中断言 task/review/invocation 归属和状态一致，上传/查询/access/export 不额外创建 invocation
- [x] 8.3 使用真实四文件样本完成浏览器演示验收，逐项核对 17 行、证据、人工复核和单 sheet Excel；输出脱敏验收记录
- [x] 8.4 运行后端目标测试、全量 pytest 和 Alembic 当前库检查，确认本 change 无 migration 且既有风险/合同审查测试不回归
- [x] 8.5 运行 `npm test`、`npm run build` 和 deployment profile tests，确认 external bundle 不暴露风控工作台
- [x] 8.6 更新 `Archi.md` 工作台/投影/导出数据流、`PLAN-internal.md` I7 进度和 `CHANGELOG.md`；ADR 无新增重大决策时只引用 ADR-015/017/018/019
- [x] 8.7 运行两个活跃 change 的 strict OpenSpec validate，确认本 change 与 ERP change 的 capabilities、non-goals 和任务没有重叠

## 9. 真实导出复核缺陷收尾

- [x] 9.1 收紧 `raw_business_mode_text` 字段定义和 ApprovalFormExtractor prompt，只从审批样表“业务性质”栏已勾选项生成“联销（预付款+联合销售）”，并增加禁止抽取“业务模式简介”的回归测试
- [x] 9.2 将已确认的“采购合同含税金额 × 保证金比例 ÷ 100”实现为确定性 `deposit_amount` 派生规则，保留输入来源和规则标识；更新投影、规则和 Excel 回归测试
- [x] 9.3 使用真实审批样表与采购合同复验业务模式、保证金和货物名称 OCR 根因，更新脱敏验收记录并运行目标测试及 strict OpenSpec validate

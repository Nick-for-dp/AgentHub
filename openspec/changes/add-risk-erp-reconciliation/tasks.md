## 1. ERP 接口契约与安全配置

- [ ] 1.1 与 ERP/业务负责人形成 `docs/risk-assistant/erp-contract-v1.md`，逐项确认测试/生产 base URL、认证、查询键、字段编码、单位、聚合截止点、错误码、SLA 和脱敏白名单
- [ ] 1.2 在 `backend/app/core/config.py` 增加 internal-only ERP enable flag、base URL、credential reference、timeout、retry 和 snapshot threshold，配置缺失时按启用状态 fail closed
- [ ] 1.3 更新 `.env.example` 只列变量名和安全说明，不写真实凭证；增加 config repr/log 测试，断言 token、Authorization 和 secret 不可见
- [ ] 1.4 在 `integrations/erp/base.py` 定义 `ErpRiskDataClient`、`ErpRiskQuery`、`ErpRiskQueryResult` 和稳定 error/status 枚举
- [ ] 1.5 在 `integrations/erp/factory.py` 实现 disabled/fake/real client 选择，测试 external profile、未授权 Agent 和 flag 关闭均不初始化真实 client

## 2. ERP snapshot 模型与迁移

- [ ] 2.1 在 `modules/risk_assessment/models.py` 增加 `RiskErpSnapshot`，字段覆盖 task、business key、接口/schema 版本、status、payload/URI、hash、queried_at 和错误摘要
- [ ] 2.2 编写 Alembic migration 创建 `risk_erp_snapshot`、task/time/status 索引和外键，执行 upgrade→downgrade→upgrade 验证
- [ ] 2.3 在 repository 中增加 snapshot create/get/list，接口只允许 insert；测试历史 snapshot 不提供覆盖 update 路径
- [ ] 2.4 在 `erp/snapshot.py` 实现白名单脱敏、稳定 JSON 序列化/hash 和小 payload JSON 保存
- [ ] 2.5 实现大 payload 转 internal MinIO 的路径，表内只保存 URI/hash；用 fake storage 测试阈值两侧和上传失败
- [ ] 2.6 增加 snapshot 权限和日志脱敏测试，断言跨任务读取、原始响应头、credential 和未脱敏字段不可泄露

## 3. ERP HTTP adapter

- [ ] 3.1 根据已确认契约在 `integrations/erp/client.py` 实现认证、request_id、timeout 和响应 schema 校验
- [ ] 3.2 实现仅对契约允许状态的有界 retry/backoff，测试 200、401、403、429、5xx、timeout 和网络中断
- [ ] 3.3 将厂商错误转换为稳定 ERP error_code/status，不把原始堆栈、URL query 或敏感 response body传入领域层
- [ ] 3.4 添加 fake client fixtures：完全匹配、数量差异、金额差异、字段缺失、ERP unavailable 和非法 schema
- [ ] 3.5 新建真实测试环境 smoke 脚本，只输出状态、字段计数、schema version 和脱敏摘要，不输出合同业务明细或凭证

## 4. ERP facts 归一化

- [ ] 4.1 在 `erp/schemas.py` 定义最小 `ErpFact` 和 snapshot summary，包含 field_code、value、unit、snapshot_id、erp_field_code 和 warnings
- [ ] 4.2 在 `erp/mapping.py` 映射主体、合同号、商品、采购/销售数量、单价、金额和日期，未配置字段显式 warning
- [ ] 4.3 实现 Decimal、日期、PERCENT、TON、CNY、CNY/TON 的确定性归一化，测试逗号、小数精度、空值和非法单位
- [ ] 4.4 按业务确认实现 ERP 多记录聚合口径和截止时间，测试重复行、撤销行、跨期记录和空集合
- [ ] 4.5 实现主体编码优先、名称仅作辅助的映射入口；在主数据规则未确认时输出 NOT_COMPARABLE，不做模糊自动合并
- [ ] 4.6 增加 mapping fixture 回归，断言 mapper 只引用 snapshot，不修改 document facts 或人工 review events

## 5. ERP comparison 规则

- [ ] 5.1 在 `rules/erp_comparison.py` 定义 ERP rule codes、outcome 和通用 check/evidence builder，保持工作台现有 check DTO 可直接读取
- [ ] 5.2 实现金额、单价、数量和日期的 exact comparison，覆盖 MATCHED/MISMATCH/ERP_MISSING/DOCUMENT_MISSING/NOT_COMPARABLE
- [ ] 5.3 实现配置化 tolerance 和 MATCHED_WITHIN_TOLERANCE（若业务确认启用），保留原始 difference、unit、tolerance 和 rule version
- [ ] 5.4 实现 ERP_UNAVAILABLE check，断言 disabled、timeout、认证失败和 schema 错误都不得序列化为 MATCHED
- [ ] 5.5 实现采购合同数量对 ERP 采购/收货数量、销售合同数量对 ERP 销售/发货数量的独立规则
- [ ] 5.6 增加负向测试，断言 comparison engine 不生成采购合同数量对销售合同数量的规则或结论
- [ ] 5.7 按关键字段策略将 comparison 转 review signal/warning，覆盖关键 ERP_MISSING 进入复核和非关键字段 warning

## 6. 正式 LangGraph 接入

- [ ] 6.1 扩展 `RiskGraphState` 增加 erp_query、erp_snapshot_summary、erp_facts 和 erp_checks，避免把完整 ERP payload 写入 checkpoint
- [ ] 6.2 新建 `build_erp_query.py`，从 business_code 和已接受合同号形成标准查询；输入不足时输出稳定 NOT_COMPARABLE/review signal
- [ ] 6.3 新建 `fetch_erp_snapshot.py`，通过 adapter 查询、脱敏并持久化 snapshot；失败路径仍返回可序列化状态
- [ ] 6.4 新建 `normalize_erp_facts.py`，只从当前 snapshot 生成 facts 和 warnings
- [ ] 6.5 新建 `run_erp_comparisons.py`，合并通用 checks/review signals 且不修改 document facts
- [ ] 6.6 直接修改 graph builder，将 ERP 节点放在 document checks 后、build review items 前，并升级 graph/schema/rule version
- [ ] 6.7 修改人工恢复路径：文档字段变更后复用同一 snapshot 重跑受影响 document/ERP checks，不再次调用 adapter
- [ ] 6.8 增加 graph 单元测试，覆盖全匹配、mismatch、ERP unavailable、关键字段缺失、人工恢复和 adapter 调用次数
- [ ] 6.9 增加演示图切换前置检查/运维说明，正式启用前要求无需要保留的演示 WAITING_REVIEW checkpoint

## 7. Result、invocation 与既有工作台契约

- [ ] 7.1 扩展 result materializer 保存 `erp_facts`、snapshot summary、ERP checks 和版本，不返回完整 payload、URI 签名或 credential
- [ ] 7.2 扩展 invocation `snapshot.runtime` 记录 snapshot id、ERP adapter/schema/rule 版本和执行状态，失败时保持 task/invocation 一致收口
- [ ] 7.3 增加 task read schema 兼容测试，确认旧字段、review_context、review_events 和业务总览 projector 不因 ERP 新键改变
- [ ] 7.4 使用当前工作台 TypeScript DTO/fixture 验证 ERP checks 能由通用 checks/evidence 组件展示，不新增 ERP 固定列或新页面
- [ ] 7.5 运行现有 Excel export 回归，断言 ERP facts 不覆盖 17 行文档/人工最终值且 workbook 仍只有“业务总览”sheet
- [ ] 7.6 增加权限与日志测试，断言前端响应、access/export、caplog 和 invocation 均不含 ERP credential 或未脱敏 payload

## 8. 生产前联调与收口

- [ ] 8.1 在 ERP 测试环境完成认证、正常查询、超时、限流、字段缺失、非法 schema 和重试次数验收
- [ ] 8.2 使用至少三组脱敏业务 fixture 验证 MATCHED、MISMATCH、ERP_MISSING 和 ERP_UNAVAILABLE 的业务口径
- [ ] 8.3 完成浏览器端到端：上传合同→正式 graph→ERP checks→WAITING_REVIEW→人工恢复→SUCCEEDED→Excel
- [ ] 8.4 验证 ERP 查询每次新任务只产生一个不可变 snapshot，人工恢复不重复查询，显式新任务产生新 snapshot
- [ ] 8.5 运行 Alembic、后端全量 pytest、前端测试/build 和 external profile import/route 回归
- [ ] 8.6 更新 `Archi.md` ERP 数据流和 snapshot 表、`PLAN-internal.md` I7、`CHANGELOG.md` 与部署环境变量文档
- [ ] 8.7 根据最终接口/策略判断是否需要新增 ADR；若未改变 ADR-015/018/019 边界，则只记录实现事实而不新增架构决策
- [ ] 8.8 运行 strict OpenSpec validate，并确认与 `add-risk-assistant-workbench-audit-export` 无工作台、Excel 或业务总览任务重叠

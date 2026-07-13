## 1. internal 前端入口与部署 profile

- [x] 1.1 新增前端 deployment profile 配置 helper、`vite-env.d.ts` 类型和 `.env.example` 示例，默认值为 `external`，并保证配置值不进入敏感日志
- [x] 1.2 在 Vue Router 中仅为 internal profile 注册 `/internal/contract-review` 登录保护路由，并补齐 direct navigation 未登录跳转行为
- [x] 1.3 调整登录后默认首页：internal 普通用户进入合同审查工作台、external 普通用户保持 `/chat`、管理员保持 admin 控制台
- [x] 1.4 为合同审查工作台增加简洁的 internal 顶栏/用户退出入口，复用现有 Session 与蓝白企业界面样式

## 2. internal 合同审查 API 与上传适配

- [x] 2.1 新增 `frontend/src/api/internalContractReview.ts`（或等价模块），定义 upload、file parse、contract review、ParsedDocument blocks、clauses/source spans/summary/warnings 的明确 TypeScript 类型
- [x] 2.2 封装 prepare upload、create/get file parse task、create/get/execute contract review task 请求，保持 `APIResponse<T>` 解包与稳定错误转换
- [x] 2.3 实现预签名 URL 的 XHR 上传 helper：应用后端 method/headers、`withCredentials=false`、支持进度与取消，且不向 MinIO 发送 AgentHub Cookie/Authorization
- [x] 2.4 为 blocking execute 增加独立长超时/取消配置，为任务查询提供有界轮询参数，避免使用全局 Axios 30 秒默认值

## 3. 审查流程状态机

- [x] 3.1 新增 `useContractReviewWorkbench` composable（或等价 service），定义 idle/preparing_upload/uploading/parsing/creating_review/reviewing/succeeded/failed 状态、阶段耗时和当前 run id
- [x] 3.2 实现 PDF/DOCX + `warehouse|transport` + `A1-A7` 输入校验，以及 prepare → upload → parse → create review → execute 的成功链路和失败短路
- [x] 3.3 对 file parse 与 contract review 非终态实现可取消的有界轮询，并在新 run 或页面卸载时清理 timer、XHR 和可取消请求
- [x] 3.4 实现 execute 响应不确定时的 read-before-retry：先 GET 收敛 SUCCEEDED/FAILED/CANCELLED/RUNNING/PENDING，再决定展示、轮询或允许用户重试
- [x] 3.5 防止重复提交和旧响应覆盖：执行中禁用不安全操作，旧 run 的迟到响应不得修改当前页面状态

## 4. source span 高亮与定位

- [x] 4.1 新增纯 TypeScript 高亮 utility，使用 Unicode code point 处理 offset，并输出普通文本/mark segments 和 presentation warnings
- [x] 4.2 校验 block、整数 offset、边界、起止顺序与 `matched_text`；对重叠 span 使用稳定非嵌套策略并为跳过片段生成 warning
- [x] 4.3 构建 block-to-span 与 clause-to-target 索引；支持有效 span 精确定位、仅 `source_block_ids` 的 block 级定位和完全无来源时的禁用态
- [x] 4.4 实现条款点击/键盘激活后的滚动与短暂聚焦样式，保证同一 block 多条命中时可区分当前条款

## 5. 合同审查工作台 UI

- [x] 5.1 实现上传与参数卡片：单文件 PDF/DOCX 控件、合同类型、A1-A7 资信等级、开始审查、重新选择与字段级错误
- [x] 5.2 实现阶段进度区：上传百分比、解析/审查阶段、已耗时、取消/安全重试和脱敏错误提示
- [x] 5.3 实现合同文档 pane：按 `result_snapshot.blocks` 顺序以纯文本渲染 block、章节/类型/id 元信息及解析 warnings，不使用 `v-html`
- [x] 5.4 实现结果摘要与条款 pane：总条款/敏感数/最高风险/warnings 指标、敏感优先与全部条款切换、风险/分类/置信度/规则/原因/来源详情
- [x] 5.5 实现“未发现敏感条款”成功空状态、结果数据缺失、高亮失败、顶层 warning 和条款 warning 的分层展示
- [x] 5.6 完成 1366px 双栏独立滚动与 1024px/375px 窄屏布局，检查键盘操作、focus、tooltip/aria label、文本溢出和语义色

## 6. 自动化测试

- [x] 6.1 为 frontend 增加 Vitest 开发依赖与 test script，不引入新的 UI 框架
- [x] 6.2 补高亮 utility 单测：中文、非 BMP 字符、合法 span、越界、反向、matched text mismatch、重叠和无 span/block fallback
- [x] 6.3 补状态机单测：各阶段成功、上传/解析/创建失败短路、旧 run 隔离、轮询终态与取消清理
- [x] 6.4 补 execute 不确定响应单测，验证 GET 查询先于任何重复 execute，且 SUCCEEDED/RUNNING/PENDING/FAILED 分支正确
- [x] 6.5 补 profile/路由回归检查，验证 external 不注册工作台入口、internal 需要登录且默认首页符合用户类型

## 7. 本地链路与 UI 验收

- [x] 7.1 运行 frontend Vitest、`vue-tsc` 和 Vite build，并分别验证 internal/external profile 构建无类型或路由错误
- [x] 7.2 验证本地 MinIO 对 internal 前端 origin 的预签名 PUT CORS 配置，确认请求未携带 AgentHub Cookie/Authorization
- [x] 7.3 使用一份运输合同完成“上传 → 解析 → 审查 → 条款定位/高亮”真实 MinIO/MySQL/Dify 全链路，核对 summary、clauses、warnings 与任务状态
- [x] 7.4 使用一份仓储合同重复真实全链路，覆盖多条高亮、无高亮 warning 或 warning 展示分支
- [x] 7.5 按 `docs/ui-review-checklist.md` 在 1366px、1024px 和 375px 截图验收 loading/empty/error/succeeded、双栏/窄屏、滚动定位和文本溢出

## 8. 文档与变更记录

- [x] 8.1 更新 README/前端环境示例与 internal 部署说明，记录 `VITE_DEPLOYMENT_PROFILE`、MinIO CORS、启动和合同审查工作台访问方式
- [x] 8.2 更新 `Archi.md`，补充 internal Web 工作台的浏览器上传、任务编排和解析文本高亮流程及模块边界
- [x] 8.3 更新 `PLAN-internal.md` I6 前端待办与验收状态，并在 `CHANGELOG.md` 记录工作台能力摘要
- [x] 8.4 复核本 change 仅引用 ADR-014/015/016/017 且未形成新的重大架构决策；若实施中边界发生变化，先更新 `DECISIONS.md` 再继续

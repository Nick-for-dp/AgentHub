## Context

`contract-review-task-handler` 已完成并归档，后端当前提供完整的 internal 合同审查链路：浏览器或系统调用方先通过 `/api/v1/internal/files/upload` 获取 MinIO 预签名 URL，上传后创建 `file_parse_task`，再创建并显式 execute `contract_review_task`。解析任务响应包含 `ParsedDocumentV1` 的 `result_snapshot`；审查任务响应包含 `clauses`、`summary`、`warnings` 和每条条款的 `source_spans`。

现有 `backend/scripts/contract_review_mvp_demo.py` 已验证一种有效的人工复核交互：左侧按 blocks 展示合同，右侧展示条款，点击条款滚动到来源 block。本 change 将该交互产品化到 Vue 前端，目标用户是 internal profile 的已登录业务用户。现有前端只有 admin 控制台和 chat 页面，尚无 internal 业务工作台路由或 internal API 客户端。

模块边界保持如下：

- frontend endpoint client：只调用 AgentHub `/api/v1/internal/*`；预签名上传 URL 只用于一次对象 PUT。
- backend endpoint/service/repository：复用现有 files、file_parse、contract_review 分层；前端不引入新的 Dify、文件解析或对象存储业务调用。
- integration client：Dify 仍只位于 `backend/app/integrations/dify`，MinIO 预签名仍由 `backend/app/integrations/object_storage` 生成，文件读取仍只位于 `backend/app/integrations/file_reader`。
- database：不增加表或字段，不需要 Alembic migration。

## Goals / Non-Goals

**Goals:**

- 提供 internal 登录用户可直接试用的单次合同审查页面。
- 将上传、解析、创建和执行任务编排为可理解、可恢复的前端状态机。
- 忠实渲染 ParsedDocument blocks 和后端规则引擎结果，完成 source span 联动高亮。
- 在长耗时和响应不确定场景中避免重复 execute，并提供明确的错误和 warning 反馈。
- 遵循现有 Vue 3、Ant Design Vue、Pinia、Vue Router、蓝白企业界面和 UI 验收规范。

**Non-Goals:**

- 不渲染原始 PDF 页面或 Word 版式，不修改原文件或生成批注文件。
- 不实现历史任务列表、分享、协同审阅、审批、报告下载或 webhook。
- 不修改合同规则、Dify workflow、TaskHandler 后端执行语义或数据库模型。
- 不把工作台推广到 external profile，也不建设跨 profile 身份系统。

## Decisions

### 1. 使用独立 internal 工作台路由，并按部署 profile 控制入口

新增 `/internal/contract-review` 页面，页面文件按计划放在 `frontend/src/pages/internal/ContractReviewPage.vue`。前端通过 `VITE_DEPLOYMENT_PROFILE`（默认 `external`）决定是否注册 internal 路由、显示入口以及非管理员用户登录后的默认首页：internal 部署进入合同审查工作台，external 部署继续进入 chat；管理员仍默认进入 admin 控制台。

选择构建时 profile，而不是通过请求失败猜测环境，是为了让 external UI 从导航和路由层面不暴露内部产品入口，并与后端 `DEPLOYMENT_PROFILE` 条件注册保持同一部署配置。部署文档和 `.env.example` 必须明确前后端 profile 值需一致。

备选方案是在所有构建中注册页面、依赖 internal API 返回 404；该方案会暴露无效入口并产生较差体验，因此不采用。首期不新增运行时配置 endpoint，避免为单页引入额外后端契约。

### 2. 前端以显式状态机编排现有 API，不新增聚合 endpoint

新增 `frontend/src/api/internalContractReview.ts` 维护请求/响应类型与以下调用：

1. prepare upload；
2. 使用预签名 URL 上传对象；
3. create/get file parse task；
4. create/get/execute contract review task。

页面逻辑抽为 `useContractReviewWorkbench` composable 或等价 service，状态至少包括 `idle`、`preparing_upload`、`uploading`、`parsing`、`creating_review`、`reviewing`、`succeeded`、`failed`。每次新提交生成新的本地 run id；旧异步响应到达时若 run id 不匹配则忽略，避免用户重新选择合同后旧请求覆盖新状态。

继续复用分步 API 可以保持上传、解析和 runtime invocation 的审计边界，也便于未来将解析/审查平移到 worker 后继续 GET 轮询。新增“一键审查”聚合 endpoint 会掩盖既有任务生命周期并扩大本 change 后端范围，因此不采用。

### 3. 预签名上传使用浏览器 XHR，不把 AgentHub 凭证发送给 MinIO

准备上传仍通过带 Cookie 的 AgentHub Axios client。真正文件上传使用独立 `XMLHttpRequest` 调用响应中的 `method`、`upload_url` 和 `headers`，`withCredentials=false`，不附带 AgentHub Authorization/Cookie。XHR 用于提供上传百分比和取消能力；不引入 MinIO SDK。

MinIO bucket 必须允许 internal 前端 origin 对预签名 PUT 所需 method/header 的 CORS。若本地或目标环境不满足，优先修正文档/MinIO CORS 配置；只有确认现有预签名契约无法浏览器使用时，才在现有 object storage integration 后增加非破坏性适配，不能让前端获得长期存储凭证。

页面首期只接受 PDF/DOCX，因为 `.doc` 当前 reader 明确要求先经 LibreOffice 转换，图片也不属于本次合同文本审查主链路。文件内容和预签名 URL 仅保存在当前页面内存，不写 localStorage/sessionStorage，不记录到前端日志。

### 4. execute 使用长请求配置，并对不确定响应执行 read-before-retry

当前 execute 是 blocking workflow，不能沿用全局 Axios 30 秒 timeout。该请求使用独立可配置超时（默认覆盖本地合同 workflow 的合理上限），页面持续显示阶段和耗时；后续若接口转异步，状态机仍以 GET 轮询终态。

当 execute 因网络、代理或客户端 timeout 失败时，错误不等于后端未执行。前端必须先 GET 当前 task：

- SUCCEEDED：直接展示结果；
- FAILED/CANCELLED：展示后端终态；
- RUNNING：继续有界轮询；
- PENDING：只有在确认仍可执行且由用户触发重试时才再次 execute。

轮询采用固定间隔加轻量退避，并设置总时限；页面离开或开始新 run 时取消 timer 和可取消请求。该策略防止盲目重复 runtime 调用和重复 invocation。

### 5. 解析文本以纯文本 block 模型渲染

成功后从 `file_parse_task.result_snapshot.blocks` 构建文档 pane。每个 block 使用稳定元素 id（例如 `contract-block-${block.id}`）和 `data-block-id`，正文通过 Vue 文本插值渲染，禁止 `v-html`。block 元信息只展示复核有用的 kind/type、section_title 和 id；解析 warnings 在独立的可折叠区域展示。

页面不尝试恢复 Word/PDF 原始版式，因为当前契约只保证解析文本及来源位置。桌面端结果区采用可调整或固定比例双栏，各 pane 独立滚动；小屏转为上下布局。

### 6. 高亮由纯函数生成安全文本 segments

新增纯 TypeScript highlight utility，输入 block text 和属于该 block 的 spans，输出普通文本段/mark 段及 presentation warnings。算法规则：

1. 使用 `Array.from(text)` 按 Unicode code point 切分，保持与 Python `len`/slice offset 语义一致；
2. 校验 block、整数 offset、`0 <= start < end <= codePointLength`；
3. 校验 `matched_text` 与切片一致；
4. 按 start/end 稳定排序；重叠 span 不生成嵌套 mark，保留可安全渲染的先到片段并为被跳过 span 生成 warning；
5. 输出始终由 Vue 文本节点和 `<mark>` 组成，不拼接 HTML 字符串。

条款卡片优先使用首个有效 span 定位；无有效 span 但有 `source_block_ids` 时只滚动到 block；两者都没有时禁用定位并显示原因。当前选中条款的 mark 与 block 使用短暂 focus 样式，并支持 button 键盘激活。

不采用前端模糊全文搜索作为自动兜底，因为相同条款可能多次出现，错误命中会削弱人工复核可信度。后端 warning 和原始来源字段仍完整展示，便于定位数据质量问题。

### 7. 结果信息以“敏感优先、全部可查”组织

顶部展示 task 状态、总条款数、敏感条款数、最高风险和 warning 数。右侧默认筛选 `is_sensitive=true`，用户可切换“全部条款”。条款卡片展示类别、风险、置信度、命中规则、判定原因和来源；风险使用语义色，不以主蓝色替代警告/错误色。

`SUCCEEDED + sensitive_clause_count=0` 显示成功空状态，而不是业务失败。顶层 warnings、条款 warnings 和前端 presentation warnings 分层展示，避免把“高亮失败”混同为“规则审查失败”。

### 8. 测试与视觉验收采用纯逻辑单测加真实页面检查

前端增加 Vitest 作为开发依赖，优先测试：Unicode offset、重叠/越界/mismatch span、无 span block 定位、状态机阶段短路、execute 不确定响应的 read-before-retry。Vue 模板继续由 `vue-tsc -b` 和 Vite build 校验；不在本 change 引入另一套 UI 框架。

实现完成后必须在 internal profile 下用至少一份运输合同和一份仓储合同走真实 MinIO/MySQL/Dify 全链路，截图检查 1366px 和窄屏布局，并逐项执行 `docs/ui-review-checklist.md`。

## Risks / Trade-offs

- [MinIO CORS 未配置导致浏览器 PUT 失败] → 在实现验收前验证预签名 URL 的 OPTIONS/PUT；将允许 origin、method 和 headers 写入 internal 部署说明，错误态区分“申请 URL 失败”和“对象上传失败”。
- [blocking execute 超过浏览器或反向代理 timeout] → 使用长请求配置、持续耗时提示和 read-before-retry；保留轮询结构以兼容未来 worker 化。
- [Python code point 与 JavaScript UTF-16 索引不同] → 高亮 utility 使用 `Array.from` code points，并以包含非 BMP 字符的单测锁定行为。
- [超长合同 blocks/条款过多导致渲染卡顿] → 避免深层响应式复制和原始 HTML，pane 独立滚动；首版不引入虚拟列表，真实样本若出现性能问题再增加窗口化。
- [构建时 profile 与后端 profile 配错] → `.env.example`、README 和部署检查明确两端必须一致；external 后端仍以 404 作为最终安全边界。
- [成功任务存在高亮 warning] → UI 将审查终态、规则结论和展示 warning 分层，既不隐藏条款，也不把成功误报为失败。

## Migration Plan

1. 增加前端 profile 配置、internal 路由/API 类型和工作台实现，不改数据库。
2. 在本地 internal 环境验证 MinIO CORS、Cookie Session、文件解析和 execute 长请求。
3. 运行前端单测与 build，并用运输/仓储样本完成真实链路和 UI checklist。
4. internal 部署设置 `VITE_DEPLOYMENT_PROFILE=internal` 后构建并发布前端；external 构建保持默认 `external`。
5. 回滚时移除 internal 前端路由/构建产物即可，现有 backend API、数据和 Dify workflow 不受影响。

## Open Questions

无阻塞问题。首版按当前同步解析、blocking execute 契约实现，同时保留非终态轮询和 read-before-retry，以兼容计划中的 arq worker 化。

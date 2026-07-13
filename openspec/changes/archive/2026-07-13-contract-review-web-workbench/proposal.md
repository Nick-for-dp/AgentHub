## Why

合同审查后端链路已经能够完成 MinIO 上传、文档解析、Dify 条款抽取、后端规则判敏与解析文本高亮，但目前业务用户只能通过 API 或本地验收脚本试用。现在需要落实 `PLAN-internal.md` I6 剩余待办 5，为 internal profile 提供一个可登录使用的合同审查辅助工作台，让用户上传合同并在同一界面复核敏感条款及其原文位置。

## What Changes

- 新增 internal profile 合同审查工作台页面，提供 PDF/DOCX 合同选择、上传状态、合同类型和对手方资信等级输入，以及开始审查操作。
- 前端通过 AgentHub internal API 依次完成预签名上传、文件解析、合同审查任务创建与执行；不直接调用 MinIO SDK、文件解析库或 Dify。
- 新增审查过程状态视图，明确展示上传、解析、审查各阶段的 loading、success 和 error 状态，并允许失败后重新选择文件或重试安全阶段。
- 新增双栏结果工作区：按 `ParsedDocumentV1.blocks` 顺序展示解析文本，展示审查摘要、敏感条款、风险等级、命中规则、判定原因和 warning。
- 使用 `source_spans` 的 `block_id + start_offset + end_offset` 对解析文本进行高亮；点击条款时滚动并聚焦对应原文，高亮无法解析时保留条款并显示排障提示。
- 为前端补充 internal API 类型、调用封装、组件级/页面级测试和 UI 验收，不改变现有合同审查规则集与 Dify workflow。

## Non-goals

- 不在原始 PDF/DOCX 文件中写入批注或按原始分页、坐标、Word run 渲染高亮；首期只展示解析文本视图。
- 不修改敏感条款规则、A1-A7 等级定义、Dify 提示词或 workflow 节点。
- 不实现合同审查历史任务列表、多人协作、审批流、报告导出或 webhook。
- 不向 external profile 暴露页面或 `/api/v1/internal/*` 能力，不建设跨 profile 登录或数据共享。

## Capabilities

### New Capabilities

- `contract-review-web-workbench`: internal profile 下合同上传、审查流程编排、解析文本展示、敏感条款列表与 source span 联动高亮的用户工作台。

### Modified Capabilities

无。工作台复用现有文件上传、文件解析和合同审查任务 API，不改变 `contract-review-task-execution` 的后端业务契约。

## Impact

- 前端：新增 internal 合同审查路由、页面与可复用的上传/进度/文本高亮/条款列表组件，扩展 `frontend/src/api/` 类型和请求封装，并调整登录后的 internal 用户默认入口或导航。
- 后端/API：原则上复用 `POST /internal/files/upload`、`POST/GET /internal/file-parse/tasks`、`POST/GET /internal/contract-review/tasks` 和显式 execute；若浏览器预签名上传暴露兼容性问题，只允许在现有对象存储抽象和 internal API 边界内做非破坏性修正。
- 安全与部署：页面和 API 仅在 `DEPLOYMENT_PROFILE=internal` 可用，使用现有 HttpOnly Cookie 登录态、任务归属和 default-deny 授权；前端不得持有 Dify API Key 或长期 MinIO 凭证。
- 架构：引用 ADR-015/ADR-016/ADR-017 的 internal profile、一次性合同解析和无 webhook 边界，以及 ADR-014 的 TaskHandler 执行抽象；本 change 不引入新的架构决策。

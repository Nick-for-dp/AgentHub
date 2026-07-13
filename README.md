# AgentHub

AgentHub 是一个 RAG 驱动的智能体应用平台。当前阶段聚焦智能问答 Agent，平台负责身份、权限、Agent 路由、知识库元数据、调用记录和可观测性，Dify 作为 MVP 阶段可替换的 runtime。

## 文档入口

| 文件 | 用途 |
|---|---|
| `Agent.md` | 大模型协作手册，Codex/Claude 优先阅读。 |
| `Archi.md` | 最新系统架构、关键流程、数据模型边界。 |
| `PLAN.md` | 当前实施计划和验收标准。 |
| `DECISIONS.md` | 架构决策记录。 |
| `CHANGELOG.md` | 已完成变更摘要。 |
| `REVIEW.md` | 主管/技术骨干 review 记录，只追加不删除。 |
| `docs/api.md` | API 说明。 |
| `docs/testing.md` | 测试策略与验收清单。 |
| `docs/deployment.md` | 本地和部署说明。 |
| `docs/frontend-design.md` | 前端设计规范。 |
| `docs/ui-review-checklist.md` | UI 验收清单。 |

## 当前状态

- 核心数据模型和 Alembic 迁移已建立。
- 已支持外部客户手机号唯一、API Key 签发、API Key 认证和权限策略。
- 已支持 Agent、知识库、文档元数据和 Agent-KB 绑定。
- 已封装 Dify runtime，支持 SSE 流式 Q&A。
- 已使用 `agent_invocation_record` 保存成功/失败调用记录。
- 已支持手机号密码登录、HttpOnly Cookie 会话、聊天页和管理端页面。
- 已支持产业互联网 iframe 嵌入主线：外部短期 JWT exchange 为 AgentHub `embed_session`，后续 iframe 请求使用 AgentHub 自己的 HttpOnly Cookie。
- 已支持云端语音识别和语音播报；浏览器录音上传 16k mono WAV，后端对接火山 ASR/TTS。
- internal profile 已支持合同审查工作台：内部用户可上传 PDF/DOCX、选择合同类型和对手方 A1-A7 资信等级，查看解析文本、规则判敏、warning 与原文 span 高亮。

当前实施细节以 `PLAN.md`、`Archi.md` 为准；这两个文件属于本地协作文档，不作为远程交付物。

## 目录结构

```text
backend/
  app/
    api/v1/endpoints/
    core/
    db/
    modules/
    integrations/
    workers/
    tests/
  scripts/

frontend/
  src/
    api/
    router/
    stores/
    layouts/
    pages/
    components/
```

## 常用命令

后端：

```powershell
cd backend
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8240
uv run pytest
```

前端：

```powershell
cd frontend
npm install
npm run dev
npm test
npm run build
```

数据库迁移：

```powershell
cd backend
uv run alembic upgrade head
```

种子数据：

```powershell
cd backend
uv run python -m scripts.seed
```

本地访问入口：

```text
AgentHub 前端：http://127.0.0.1:3000
AgentHub 管理后台：http://127.0.0.1:3000/admin
AgentHub 后端：http://127.0.0.1:8240
```

## 内部合同审查工作台

合同审查页面仅用于 internal profile。前端构建配置必须与后端 `DEPLOYMENT_PROFILE` 一致：

```text
# backend/.env
DEPLOYMENT_PROFILE=internal
CORS_ALLOWED_ORIGINS=http://127.0.0.1:3000

# frontend/.env（可从 frontend/.env.example 复制）
VITE_DEPLOYMENT_PROFILE=internal
VITE_CONTRACT_REVIEW_EXECUTE_TIMEOUT_MS=600000
```

启动后，内部登录用户访问 `http://127.0.0.1:3000/internal/contract-review`。页面只调用
AgentHub internal API；文件本体通过后端签发的一次性 MinIO 预签名 URL 上传，浏览器不会向
MinIO 发送 AgentHub Cookie、Authorization 或 Dify 凭证。MinIO bucket 需为前端 origin 放行
`PUT` / `OPTIONS` 和预签名请求要求的 `Content-Type` header，详细部署要求见 `docs/deployment.md`。

## 产业互联网 iframe 嵌入

嵌入链路采用“外部短期 JWT 只用于 exchange，AgentHub 自己维护 iframe session”的设计：

1. 产业互联网父页面打开 `/embed/chat?agent=qa`。
2. iframe 启动后发送 `AGENTHUB_TOKEN_REQUIRED`，消息中包含一次性 `request_id`。
3. 父页面收到后向产业互联网后端申请全新的短期 embed token，并通过 `postMessage` 回传同一个 `request_id`。
4. iframe 只接受当前等待中的 `request_id`，随后调用 `POST /api/v1/embed/exchange`。
5. AgentHub 后端验证 JWT 的签名、`iss`、`aud`、`exp`、`typ`、`scope`、`agent_code` 和用户信息，验证通过后写入 `agenthub_embed_session` HttpOnly Cookie。
6. iframe 后续聊天、会话、语音接口只使用 AgentHub embed session Cookie，并携带 `X-AgentHub-Embed: true`。
7. iframe 会在 `embed_session` 到期前 180 秒重新向父页面请求一次性 token，用新 token 续建 AgentHub embed session。
8. 父页面登出或关闭 iframe 时发送 `AGENTHUB_AUTH_CLEARED`，iframe 调用 `/api/v1/embed/logout` 清理当前 embed session。

token 传递约束：

- 父页面与 iframe 之间的每次 token 请求必须绑定一个新的 `request_id`。
- 父页面不能缓存或复用已发送的 embed token；同一个 `request_id` 只能签发并发送一次。
- iframe 收到 token 后立即清空 pending `request_id`；重复回包、旧回包或不匹配回包必须忽略。
- iframe 在当前页面生命周期内记录已消费的 JWT `jti`，相同 `jti` 不会再次 exchange。
- 生产环境必须使用 HTTPS，并配置严格的 `EMBED_ALLOWED_PARENT_ORIGINS` / `VITE_EMBED_ALLOWED_PARENT_ORIGINS`，避免 `postMessage` 被非预期 origin 接收。

本地联调用的产业互联网 Mock 属于个人开发工具，放在 `devtools/` 下并已被 `.gitignore` 忽略，不上传远程仓库。

## 关键约束

- 前端和业务模块不得直接调用 Dify。
- 登录 token 和 API Key 都必须解析为统一 `AuthenticatedSubject`。
- 权限默认拒绝。
- 每次 Agent 调用必须写入 `agent_invocation_record`。
- 密码、token、API Key 原文不得日志、响应或落库。
- iframe embed token 只允许短期、一次性传递和消费；业务请求不得长期携带外部 token。

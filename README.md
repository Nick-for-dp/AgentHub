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
- 前端已有基础聊天页和管理端页面。

当前新主线见 `PLAN.md`：手机号密码登录、Dify 节点事件过程展示、语音输入和回复播报。

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

## 关键约束

- 前端和业务模块不得直接调用 Dify。
- 登录 token 和 API Key 都必须解析为统一 `AuthenticatedSubject`。
- 权限默认拒绝。
- 每次 Agent 调用必须写入 `agent_invocation_record`。
- 密码、token、API Key 原文不得日志、响应或落库。

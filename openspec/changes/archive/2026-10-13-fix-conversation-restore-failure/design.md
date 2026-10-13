## Context

外部客户打开聊天页时，`onMounted` → `restoreCurrentConversation`（`frontend/src/pages/chat/ChatPage.vue`）会根据 URL `conversation_id` 或 `getCurrentConversation` 恢复历史会话。Review 发现三条缺陷：

1. **恢复路径对失效会话 ID 零容错**：URL 残留已删除/不存在的 `conversation_id` 时，`getConversation` / `getConversationMessages` 返回 404，前端整个 `try/catch` 落进 `catch` 弹"抱歉，出错了"，且 URL 不清、每次刷新重蹈覆辙。后端聊天入口 `ensure_active_conversation`（`backend/app/modules/conversation/service.py`）对失效 ID 是"静默回退到当前/新建"，恢复路径与之一致性缺失。
2. **恢复路径 401 不重定向**：`send()` 收到 401 会清理登录态并跳 `/login`，但 `restoreCurrentConversation` 的 `catch` 只设 `errorMsg`，非 embed 用户会被"抱歉，出错了"卡在聊天页。
3. **后端可能写入 NULL `steps`**：`update_message`（`service.py:209`）用 `exclude_unset=True` 后对 payload 字段直接 `setattr`；若调用方显式传 `steps=None`，会把 NULL 写进 `conversation_message.steps`（列 nullable=False 且无 server default，ORM default 只在 INSERT 时生效）。后续 `ConversationMessageRead.model_validate` 对 `steps: list[dict]` 校验 NULL 直接 500。

约束：不改用户可见错误文案契约（沿用"抱歉，出错了"）；不触碰 Dify 调用、权限默认拒绝、embed 鉴权等红线；无数据库结构变更。

## Goals / Non-Goals

**Goals:**
- 恢复会话遇"会话不存在/已删除"时，静默清 URL 并回退到当前会话（没有再新建/空会话），不弹错误。
- 非 embed 模式恢复路径 401 与 `send()` 对齐：清理登录态 + 跳 `/login`。
- 后端 `update_message` 把显式 `steps=None` 归一为 `[]`，阻止新写 NULL。
- 前端测试覆盖上述回退与 401 重定向路径。

**Non-Goals:**
- 不改"抱歉，出错了"统一文案及其余错误分支（403/503/网络错误等维持现状）。
- 不做存量脏数据（已存在 NULL steps 行）的迁移回填；如后续需要单独立项。
- 不评估/改造 embed 模式 agent 绑定 403 场景（另立 change）。
- 不改 `get_user_conversation` 抛 404 的后端语义（404 是正确契约，容错应在消费方）。

## Decisions

### D1: 前端恢复路径单独捕获 404 并回退，而非吞掉所有错误

`restoreCurrentConversation` 内对 `getConversation(requestedId)` / `getConversationMessages(requestedId)` 用独立 `try/catch`：仅当错误 `status === 404` 时视为"会话失效"，执行 `syncConversationUrl(null)` 清 URL 后回退到 `getCurrentConversation(agentCode)` 取当前会话（不存在则 `current = null`，页面进入空会话态，与 `restoreCurrentConversation` 现有空态分支一致）。其他错误继续冒泡到外层 `catch` 保持现状。

- 备选 A：改后端让 `get_user_conversation` 对失效 ID 返回空而不是 404 —— 拒绝。404 是正确契约（`docs/api.md` 与既有调用方均依赖），且会影响越权检测语义。
- 备选 B：前端在 `catch` 里统一忽略 404 —— 拒绝。会把 403（embed 越权）等一并吞掉，破坏安全边界。

### D2: 恢复路径 401 走与 `send()` 一致的重定向

`restoreCurrentConversation` 的 `catch` 增加 401 分支：非 embed 模式 `auth.clearSession()` + `router.push('/login')`；embed 模式维持现状（由 embed token 重取流程接管，`activateEmbedSession`/`restoreEmbedSession` 已覆盖）。该分支同样沿用统一文案"抱歉，出错了"。

### D3: 后端 `update_message` 归一化 `steps`

在 `update_message` 应用 `update_data` 前，对 `steps` 字段做归一：`update_data["steps"] = update_data["steps"] or []`（仅当 key 存在时）。成本一行，防御显式 `None`；与 `ConversationMessageUpdate.steps` 的类型（`list | None`）兼容。不改 ORM 模型、不引入 migration。

## Risks / Trade-offs

- [前端 404 判断依赖 axios 错误结构 `error.response?.status`] → 前端已有 `http.ts` 拦截器，`getConversation` 等通过同一 `http` 实例，错误带 `status`；仅当 `status === 404` 时回退，不会误伤 403/网络错误。
- [回退后 `getCurrentConversation` 本身也可能失败] → 让该调用继续由外层 `catch` 兜底（弹统一文案），不额外吞错。
- [`update_message` 归一 `steps=None` 可能掩盖调用方意图] → 本 change 内所有调用方传 `steps=[]` 或 `handler._node_trace`（list），显式 `None` 属异常值；归一为 `[]` 符合"steps 恒为列表"的不变量。

## Migration Plan

无数据库结构变更，无需迁移。部署顺序：前端与后端各自独立可回滚（前端 404/401 逻辑、后端 `update_message` 归一），任一单独发布均安全。存量 NULL steps 行不在本 change 处理范围。

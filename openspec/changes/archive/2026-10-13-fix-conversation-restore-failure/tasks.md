## 1. 前端恢复路径容错（ChatPage.vue）

- [x] 1.1 `frontend/src/pages/chat/ChatPage.vue` `restoreCurrentConversation`：将 `getConversation(requestedId)` / `getConversationMessages(requestedId)` 的调用包进独立 `try/catch`，仅当错误 `status === 404` 时执行 `syncConversationUrl(null)` 清 URL，并回退调 `getCurrentConversation(agentCode)` 取当前会话；回退后无当前会话则保持空会话态，不弹"抱歉，出错了"。非 404 错误继续抛给外层 `catch`。
- [x] 1.2 `frontend/src/pages/chat/ChatPage.vue` `restoreCurrentConversation` 外层 `catch`：增加 401 分支——非 embed 模式执行 `auth.clearSession()` + `router.push('/login')`，错误文案仍为"抱歉，出错了"；embed 模式维持现状（不额外跳转，由 embed token 重取流程接管）。

## 2. 后端 steps 空值归一（conversation service）

- [x] 2.1 `backend/app/modules/conversation/service.py` `update_message`：应用 `update_data` 前，当 `steps` 键存在且值为 `None` 时归一为 `[]`（仅键存在时处理，不改变 `exclude_unset=True` 语义）。

## 3. 前端测试

- [x] 3.1 `frontend/src/pages/chat/ChatPage.test.ts`：新增用例——`getConversation` 返回 404 时页面清除 URL `conversation_id`、回退加载当前会话、`error-message` 不出现"抱歉，出错了"。
- [x] 3.2 `frontend/src/pages/chat/ChatPage.test.ts`：新增用例——`getCurrentConversation` 回退后无会话时进入空会话态且无错误提示。
- [x] 3.3 `frontend/src/pages/chat/ChatPage.test.ts`：新增用例——非 embed 恢复会话收到 401 时执行 `clearSession` 并跳转 `/login`，文案仍为"抱歉，出错了"。

## 4. 后端测试

- [x] 4.1 `backend/app/tests/unit/test_conversation_service.py`：新增用例——`update_message` 显式传 `steps=None` 时落库值为 `[]` 而非 NULL；`steps` 未传时行为不变。

## 5. 质量门与验证

- [x] 5.1 前端验证：`cd frontend && npm test` 全绿，`npm run build` 成功。
- [x] 5.2 后端验证：`cd backend && uv run pytest` 全绿，`uv run ruff check` 无错误。
- [x] 5.3 人工冒烟（如有条件）：打开带失效 `conversation_id` 的 URL，确认自动回退不弹错；登录态过期时打开聊天页，确认跳转 `/login`。

## 6. 文档归档（阿基执行）

- [ ] 6.1 变更摘要更新到 `CHANGELOG.md`；如影响架构事实，同步 `Archi.md`（本 change 预期无架构事实变化）。
- [ ] 6.2 归档 change，delta spec 合并入 `openspec/specs/chat-experience/` 与 `openspec/specs/conversation-restore-resilience/`。

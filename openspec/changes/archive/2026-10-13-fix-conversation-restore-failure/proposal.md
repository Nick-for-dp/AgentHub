## Why

外部客户打开聊天页时，若 URL 残留已删除/不存在的 `conversation_id`（用户换设备删除会话、管理端软删、或数据库重建后旧 URL 仍被收藏），前端 `restoreCurrentConversation` 直接把 `getConversation` 的 404 当作硬错误，弹出"抱歉，出错了"且 URL 不清、每次刷新重蹈覆辙。这与后端聊天入口 `ensure_active_conversation` 对失效 ID 静默回退的既有契约不一致，属于功能缺陷而非单纯数据缺失。

## What Changes

- `frontend/src/pages/chat/ChatPage.vue` `restoreCurrentConversation`：对 `getConversation` / `getConversationMessages` 的 404（会话不存在或已删除）单独处理——清掉 URL 里的 `conversation_id`，回退到 `getCurrentConversation` 取当前会话，没有再新建/空会话，不再弹错误。
- `frontend/src/pages/chat/ChatPage.vue` `restoreCurrentConversation`：非 embed 模式恢复路径收到 401 时，与 `send()` 对齐——清理登录态并跳转 `/login`，而不是只弹"抱歉，出错了"卡在聊天页。
- `backend/app/modules/conversation/service.py` `update_message`：显式传入 `steps=None` 时归一为 `[]`，避免把 NULL 写入 `conversation_message.steps`，从根上消除后续 `ConversationMessageRead.model_validate` 对 NULL 校验失败导致的 500。
- 补充前端测试覆盖上述恢复回退与 401 重定向路径。

## Capabilities

### New Capabilities

- `conversation-restore-resilience`: 聊天页会话恢复对失效会话 ID 的容错回退、401 重定向、以及后端 steps 空值归一化。

### Modified Capabilities

- `chat-experience`: 扩展"会话操作失败"需求——恢复会话遇到"会话不存在/已删除"时不得视为硬错误弹"抱歉，出错了"，MUST 静默回退到当前/新建会话。

## Impact

- `frontend/src/pages/chat/ChatPage.vue`（恢复逻辑）、`frontend/src/pages/chat/ChatPage.test.ts`（测试）。
- `backend/app/modules/conversation/service.py`（`update_message` steps 归一）。
- 无数据库结构变更，无 API 契约破坏；不影响 embed 鉴权、权限默认拒绝、调用记录等红线。

## Non-goals

- 不改会话恢复外的错误文案统一逻辑（沿用"抱歉，出错了"契约）。
- 不做存量脏数据（已有 NULL steps 行）的迁移回填——本 change 只阻止新写入 NULL。
- 不评估/改造 embed 模式 agent 绑定 403 场景（如需要另立 change）。

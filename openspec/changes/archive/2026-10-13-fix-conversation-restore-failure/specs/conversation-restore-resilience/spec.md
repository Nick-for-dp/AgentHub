## ADDED Requirements

### Requirement: 会话恢复对失效会话 ID 容错回退

聊天页恢复历史会话时，若 URL 中的 `conversation_id` 指向不存在或已删除的会话（后端返回 404），页面 MUST NOT 视为硬错误，MUST 清除 URL 中的失效 `conversation_id`，并回退到当前会话；当前会话不存在时 MUST 进入空会话状态，不弹用户可见错误。

#### Scenario: URL 残留已删除会话 ID

- **WHEN** 用户打开带 `conversation_id` 的聊天页 URL，且该会话已被删除或不存在（恢复接口返回 404）
- **THEN** 页面清除 URL 中的 `conversation_id`
- **AND** 回退加载该 Agent 下当前会话，不显示"抱歉，出错了"

#### Scenario: URL 残留失效会话 ID 且无当前会话

- **WHEN** 用户打开带失效 `conversation_id` 的聊天页 URL，且该用户在该 Agent 下没有 ACTIVE 会话
- **THEN** 页面进入空会话状态，可正常发起新对话，不显示"抱歉，出错了"

### Requirement: 会话恢复 401 重定向

非 embed 模式聊天页恢复会话收到 401 时，页面 MUST 清理失效登录态并跳转登录页，与发送消息路径行为一致。

#### Scenario: 非 embed 恢复会话鉴权过期

- **WHEN** 普通登录用户打开聊天页恢复会话，后端返回 401
- **THEN** 页面清理登录态并跳转 `/login`
- **AND** 用户可见错误提示仍为"抱歉，出错了"

### Requirement: 会话消息 steps 拒绝 NULL 写入

后端更新会话消息时，显式传入的 `steps` 为 NULL MUST 归一化为空列表再落库，禁止向 `conversation_message.steps` 写入 NULL。

#### Scenario: steps 显式传 NULL

- **WHEN** 更新会话消息且 `steps` 字段显式传入 `null`
- **THEN** 落库值为空列表 `[]`
- **AND** 后续读取该消息的 steps 校验不因 NULL 失败

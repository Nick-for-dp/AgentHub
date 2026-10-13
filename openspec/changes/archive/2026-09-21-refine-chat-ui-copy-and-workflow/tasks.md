## 1. 对话页文案与工作流展示

- [x] 1.1 `frontend/src/pages/chat/ChatPage.vue`：embed 未登录提示由“请先登录官网”改为“请先登录”，普通模式登录入口保持可点击。
- [x] 1.2 `frontend/src/pages/chat/ChatPage.vue`：空会话欢迎语改为“请提问”，移除欢迎语中的 `agentCode` 插值。
- [x] 1.3 `frontend/src/pages/chat/ChatPage.vue`：新建流式消息、历史消息恢复、切换会话和新建会话默认均不展开节点明细；摘要卡片保留，用户可手动展开。
- [x] 1.4 `frontend/src/pages/chat/ChatPage.vue`：`getWorkflowTitle` 的 running 分支改为“正在搜索”，finished/failed 文案保持不变。

## 2. 统一错误提示

- [x] 2.1 `frontend/src/pages/chat/ChatPage.vue`：集中定义用户可见错误文案“抱歉，出错了”，避免各分支重复硬编码。
- [x] 2.2 将发送消息 401/403/503/其他错误、embed 鉴权失败/过期、会话恢复/切换/删除失败、语音输入失败的 `errorMsg` 赋值统一为“抱歉，出错了”。
- [x] 2.3 保留 401 登录态清理或 embed token 重取、403/503 错误状态收敛、语音错误关闭和请求降级等原有控制流；后端 API、SSE 契约、日志和调用记录不改动。

## 3. 测试与验证

- [x] 3.1 新增 `frontend/src/pages/chat/ChatPage.test.ts`：覆盖 embed/普通未登录“请先登录”和空会话“请提问”。
- [x] 3.2 新增工作流展示测试：默认折叠节点明细、摘要可展开、running 标题为“正在搜索”、finished/failed 标题不变。
- [x] 3.3 新增代表性错误测试：请求或流式错误时显示“抱歉，出错了”；401 清理/重新授权行为仍执行。
- [x] 3.4 前端验证：`cd frontend && npm test` 全绿，`npm run build` 成功。
- [x] 3.5 UI 冒烟：按 `docs/ui-review-checklist.md` 检查桌面 1366px 与移动端 375px 的未登录、空会话、运行中和错误态，确认无文本溢出、遮挡或输入区位移。

## 4. 文档与归档

- [x] 4.1 阿基执行：更新 `docs/frontend-design.md`，明确工作流节点明细默认折叠、摘要保留且可手动展开。
- [x] 4.2 阿基执行：更新 `docs/embed-token-sequence.mmd` 中“请先登录官网”为“请先登录”。
- [x] 4.3 阿基执行：评审实现与测试结果，更新 `CHANGELOG.md`，归档 change 并将 delta spec 合并到 `openspec/specs/chat-experience/spec.md`。

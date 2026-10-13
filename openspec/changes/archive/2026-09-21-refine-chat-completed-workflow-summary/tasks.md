## 1. 实现

- [x] 1.1 `frontend/src/pages/chat/ChatPage.vue`：`getWorkflowTitle()` 的 finished 分支由“工作流已完成”改为“已完成”。
- [x] 1.2 `frontend/src/pages/chat/ChatPage.vue`：完成态不渲染“最近完成：…”副标题；运行态“正在处理/重试”和失败态节点提示保持不变。
- [x] 1.3 保持完成态步数、节点明细默认折叠及展开/收起行为不变。

## 2. 测试与验证

- [x] 2.1 更新 `frontend/src/pages/chat/ChatPage.test.ts`：完成态摘要标题为“已完成”，且不显示“最近完成”。
- [x] 2.2 补运行态断言：摘要仍显示“正在搜索”和当前处理节点详情。
- [x] 2.3 `cd frontend && npm test` 全绿，`npm run build` 成功。
- [x] 2.4 浏览器冒烟：完成真实问答后确认只显示“已完成”和步数，节点明细仍可手动展开。

## 3. 文档与归档

- [x] 3.1 阿基执行：评审实现与测试，更新 `CHANGELOG.md` 并归档 change，将 delta spec 合并到 `openspec/specs/chat-experience/spec.md`。

## 双 profile 登录页 UI 验收记录

- 验收日期：2026-07-21
- 构建命令：`npm run build:profiles`
- 自动化检查：`npm test`（9 个测试文件、34 个测试通过），`npm run check:profile-builds` 通过
- 静态预览：external `http://127.0.0.1:4173/`，internal `http://127.0.0.1:4174/`

### 视口与结果

| Profile | 1366×768 | 375×812 | 错误态 | 结果 |
| --- | --- | --- | --- | --- |
| external | 品牌为“AgentHub 营销智能体”，用途为“产品咨询与营销问答服务” | 卡片、标题、表单及按钮均未横向溢出 | 提交失败后显示“登录失败，请稍后重试” | 通过 |
| internal | 品牌为“AgentHub 内部智能体”，用途为“合同审查与风控工作台” | 卡片、标题、表单及按钮均未横向溢出 | 提交失败后显示“登录失败，请稍后重试” | 通过 |

本地截图保存在 `frontend/tmp/ui-review/*-latest.png`（该目录为本地 QA 临时产物，不纳入版本控制）。验收过程中发现 `a-alert` 使用默认插槽时只显示图标而不显示错误文字，已改为通过 `message` 属性传入错误内容，并在重新构建后复验通过。

### 构建隔离结论

- external 产物包含 external 登录品牌和 `/chat` 默认入口。
- external 产物不包含 `/internal/contract-review`、合同审查/风控文案或 internal 页面 chunk。
- internal 产物包含合同审查、风控助手页面 chunk及 internal 登录品牌。
- `dist/external` 与 `dist/internal` 连续构建，第二次构建未清空另一 profile 的产物。

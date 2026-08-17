## Why

`DECISIONS.md` ADR-020 已决策：AgentHub 原同时承载对外（external）和对内（internal）智能体平台，对内部分已单向抽离到独立项目 Citadel。AgentHub 收敛为纯对外智能体平台。

本文档对应 PLAN.md 之外的新增执行事项：ADR-020 代码层落地的 Phase 2（前端切除），瘦身阶段划分见 `ag.md` §5。姊妹提案：`slim-backend-external-only`（Phase 1，后端切除）、`slim-deploy-single-instance`（Phase 3，deploy 切除）。三者技术解耦，可独立评审、独立验证、独立回滚。

文档体系（Phase 4）已由架构师重写为 external-only target 状态，但**前端代码仍停留在双 profile 形态**——25 个 internal 文件（合同审查页、风控工作台、InternalLayout 等）仍在仓库，`VITE_DEPLOYMENT_PROFILE` + `__INTERNAL_BUILD__` 编译期常量与 `dist/external`、`dist/internal` 双产物构建链路仍在 `vite.config.ts` / `package.json` 中。本提案收口前端代码层的切除与构建收敛，使前端代码事实与文档事实对齐。

现在做是因为：双 profile 构建链路增加前端构建复杂度；internal 页面依赖的 `/api/v1/internal/*` 路由由 Phase 1 移除后，前端 internal 残留页面彻底失去存在意义。external 产物本就不含 internal 页面（编译期排除），两个提案落地顺序不影响 external 可用性。

## What Changes

### 前端切除

- 删除 25 个纯 internal 文件：`pages/internal/`、`components/contract-review/`、`components/risk-assistant/`、`layouts/InternalLayout.vue`、`api/internal*.ts`（3+2 测试）、`composables/use{ContractReview,RiskAssistant}Workbench.*`、`utils/contractHighlight.*`。
- 掏空 6 个共享文件：`router/routes.ts`、`config/deploymentProfile.ts`（整删，品牌文案收敛常量）、`stores/auth.ts`、`pages/auth/LoginPage.vue`、`vite-env.d.ts`、`deploymentProfile.test.ts`。
- 构建收敛：删 `build:external`/`build:internal`/`build:profiles`/`check:profile-builds` script + `scripts/build-profiles.mjs` + `check-profile-builds.mjs`；`vite.config.ts`/`vitest.config.ts` 去 `__INTERNAL_BUILD__`/`VITE_BUILD_OUT_DIR`，单产物 `dist`；`.env.example` 删 3 条目；清 `frontend/tmp-*.log`、`frontend/tmp/ui-review/`。

### DEPLOYMENT_PROFILE 机制移除（前端）

前端 `VITE_DEPLOYMENT_PROFILE` 环境变量、`__INTERNAL_BUILD__` 编译期常量、双产物构建全部删除，构建产物固定为单 `dist`。后端侧 `DEPLOYMENT_PROFILE` 枚举/配置/条件路由的移除由姊妹提案 `slim-backend-external-only` 收口。

## Capabilities

### New Capabilities

- `external-only-platform`：新增「前端单产物构建」验收需求。该能力的其余需求（单部署形态、固定 Cookie 名、不引入 internal 依赖）由姊妹提案 `slim-backend-external-only` 提供，归档时合并为同一能力规格。

### Modified Capabilities

无。本提案不改变 external 前端任何页面行为，只删除 internal 资产并收敛构建。

## Impact

- **受影响代码**：前端 25 个文件删除 + 6 个共享文件掏空；构建脚本与配置收敛。
- **构建**：`npm run build` 产出单一 `dist`，无 `dist/external`/`dist/internal`；`build:external` 等四个 script 与两个构建脚本删除。
- **受影响 API**：无。前端不调用的 `/api/v1/internal/*` 移除属姊妹提案 `slim-backend-external-only`；external API 契约不变。
- **测试**：internal 页面/组件/composable 测试随源文件一并删除，剩余 external 测试必须全绿。
- **文档**：Phase 4 已完成文档重写，本提案不重复改文档；实现完成后只需在 `CHANGELOG.md` 追加前端切除摘要并归档本 change。

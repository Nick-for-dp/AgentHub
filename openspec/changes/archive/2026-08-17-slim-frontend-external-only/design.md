## Context

前端用 `VITE_DEPLOYMENT_PROFILE` + `__INTERNAL_BUILD__` 编译期常量做双产物构建（`dist/external`、`dist/internal`）：`vite.config.ts` 按 profile 决定 `define.__INTERNAL_BUILD__` 与 `VITE_BUILD_OUT_DIR`；`router/routes.ts` 的 `createAppRoutes(profile)` 按 profile 条件注册 internal 路由；`config/deploymentProfile.ts` 提供按 profile 切换的品牌文案；`stores/auth.ts` 的 `defaultHomePath` 按 profile 分派。internal 资产共 25 个文件（`pages/internal/`、`components/contract-review/`、`components/risk-assistant/`、`layouts/InternalLayout.vue`、`api/internal*.ts`、`composables/use*Workbench.*`、`utils/contractHighlight.*`）。

文档层（Phase 4）已由架构师重写为 external-only target 状态（ADR-020、Archi.md 去 internal 章节、Agent.md 红线精简、PLAN-internal.md 删除）。本设计收口前端代码层切除与构建收敛；后端切除见姊妹提案 `slim-backend-external-only`，deploy 切除见 `slim-deploy-single-instance`。

internal 页面依赖的后端 `/api/v1/internal/*` 由 Phase 1 移除；external 产物本就通过编译期常量排除 internal 页面，两个提案落地顺序不影响 external 可用性。前端测试与构建自洽验证，不依赖后端是否已切除。

## Goals / Non-Goals

**Goals:**
- 前端 internal 文件全量切除，共享文件掏空 internal 分支，external 页面（登录/聊天/管理端/embed）行为不变。
- 构建收敛为单产物 `dist`，删除双产物脚本与编译期常量。
- `npm test` 全绿、`npm run build` 成功，grep 守卫确认无 internal 残留引用。

**Non-Goals:**
- 不改动 external 页面的 UI、交互与 API 调用。
- 不改动 SSE 事件契约与 `StreamEvent` 类型。
- 不引入新依赖、新页面、新能力。
- 后端 internal 切除（姊妹提案 `slim-backend-external-only`）；deploy 模板切除（姊妹提案 `slim-deploy-single-instance`）。

## Decisions

### D1. 前端构建收敛为单产物 dist

删除 `build:external`/`build:internal`/`build:profiles`/`check:profile-builds` 四个 script 与 `scripts/build-profiles.mjs`、`scripts/check-profile-builds.mjs`。`vite.config.ts` 删除 `isInternalBuild`、`__INTERNAL_BUILD__` define、`VITE_BUILD_OUT_DIR`，输出固定为 `dist`。`vitest.config.ts` 删除 `__INTERNAL_BUILD__` define。`vite-env.d.ts` 删除三个 internal 相关声明。

`config/deploymentProfile.ts` 整个文件删除，品牌文案（productName/subtitle）收敛为 `LoginPage.vue` 内常量。`router/routes.ts` 删除 `createAppRoutes(profile)` 的 profile 参数与 internal 条件块。`stores/auth.ts` 的 `defaultHomePath` 固定 `/chat`（admin `/admin/agents`）。

### D2. internal 文件与共享文件的切除边界

删除清单以「只被 internal 链路引用」为准：25 个纯 internal 文件整删；6 个共享文件掏空时保留 external 逻辑——`routes.ts` 无条件注册 external 路由、`auth.ts` 的 `defaultHomePath` 固定 `/chat`（admin `/admin/agents`）、`LoginPage.vue` 品牌文案收敛为组件内常量并移除 `deploymentPresentation` 依赖。

## Risks / Trade-offs

- [前端构建配置改动可能破坏 build] -> `npm run build` + `npm test` 验证单产物构建；删除 `__INTERNAL_BUILD__` 后确认无残余引用。
- [共享文件掏空可能误删 external 逻辑] -> `routes.ts`/`auth.ts`/`LoginPage.vue` 改动逐文件 review；现有 external 测试作回归基线。
- [internal 文件删除遗漏交叉引用] -> grep 守卫（`__INTERNAL_BUILD__`、`VITE_DEPLOYMENT_PROFILE`、`internalContractReview`、`internalRiskAssistant`、`InternalLayout` 零残留）兜底。

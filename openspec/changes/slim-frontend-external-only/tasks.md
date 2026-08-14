## 1. 前端 internal 文件切除

- [ ] 1.1 删除 `frontend/src/pages/internal/`（ContractReviewPage.vue、RiskAssistantPage.vue、RiskAssistantPage.test.ts）
- [ ] 1.2 删除 `frontend/src/components/contract-review/`（ReviewDocumentPane.vue）
- [ ] 1.3 删除 `frontend/src/components/risk-assistant/`（7 个 vue + 2 个 test）
- [ ] 1.4 删除 `frontend/src/layouts/InternalLayout.vue`
- [ ] 1.5 删除 `frontend/src/api/internalContractReview.ts`、`internalRiskAssistant.ts`、`internalFiles.ts` 及对应 `.test.ts`
- [ ] 1.6 删除 `frontend/src/composables/useContractReviewWorkbench.ts`、`useRiskAssistantWorkbench.ts` 及对应 `.test.ts`
- [ ] 1.7 删除 `frontend/src/utils/contractHighlight.ts` 及 `.test.ts`
- [ ] 1.8 删除 `frontend/src/config/deploymentProfile.ts` 及 `.test.ts`

## 2. 前端共享文件掏空与构建收敛

- [ ] 2.1 `frontend/src/router/routes.ts`：删除 `createAppRoutes(profile)` 的 profile 参数与 internal 条件块（`:62` `if (__INTERNAL_BUILD__ && profile === 'internal')`）；路由无条件注册
- [ ] 2.2 `frontend/src/stores/auth.ts`：`defaultHomePath` 固定 `/chat`（admin `/admin/agents`），移除对 `deploymentProfile.ts` 的 import
- [ ] 2.3 `frontend/src/pages/auth/LoginPage.vue`：品牌文案（productName/subtitle）收敛为组件内常量，移除 `deploymentPresentation` 依赖
- [ ] 2.4 `frontend/src/vite-env.d.ts`：删除 `__INTERNAL_BUILD__`、`VITE_DEPLOYMENT_PROFILE`、`VITE_CONTRACT_REVIEW_EXECUTE_TIMEOUT_MS` 声明
- [ ] 2.5 `frontend/vite.config.ts`：删除 `isInternalBuild`、`define.__INTERNAL_BUILD__`、`VITE_BUILD_OUT_DIR`；输出固定 `dist`
- [ ] 2.6 `frontend/vitest.config.ts`：删除 `__INTERNAL_BUILD__` define
- [ ] 2.7 `frontend/package.json`：删除 `build:external`、`build:internal`、`build:profiles`、`check:profile-builds` 四个 script
- [ ] 2.8 删除 `frontend/scripts/build-profiles.mjs`、`frontend/scripts/check-profile-builds.mjs`
- [ ] 2.9 `frontend/.env.example`：删除 `VITE_DEPLOYMENT_PROFILE`、`VITE_BUILD_OUT_DIR`、`VITE_CONTRACT_REVIEW_EXECUTE_TIMEOUT_MS` 条目
- [ ] 2.10 清理 `frontend/tmp-*.log`（4 个）、`frontend/tmp/ui-review/`

## 3. 验证

- [ ] 3.1 前端：`cd frontend && npm install && npm test` 全绿
- [ ] 3.2 前端：`npm run build` 单产物 `dist` 成功
- [ ] 3.3 前端 grep 守卫：`__INTERNAL_BUILD__`、`VITE_DEPLOYMENT_PROFILE`、`VITE_BUILD_OUT_DIR`、`internalContractReview`、`internalRiskAssistant`、`InternalLayout` 零残留
- [ ] 3.4 冒烟：登录页 `/login` 与聊天页 `/chat` 可达
- [ ] 3.5 `CHANGELOG.md` 追加前端切除摘要；归档本 change 到 `openspec/specs/`

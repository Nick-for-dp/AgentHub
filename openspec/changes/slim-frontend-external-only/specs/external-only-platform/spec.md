# external-only-platform

## ADDED Requirements

### Requirement: 前端单产物构建

前端 MUST 只产生一个构建产物 `dist`，MUST 不区分 external/internal，MUST 不使用 `__INTERNAL_BUILD__` 编译期常量。

#### Scenario: 单产物构建

- WHEN 执行 `npm run build`
- THEN 产物位于 `frontend/dist`
- AND 不存在 `frontend/dist/external` 或 `frontend/dist/internal`
- AND 构建产物不含 `ContractReviewPage`、`RiskAssistantPage`、`InternalLayout`

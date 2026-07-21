## ADDED Requirements

### Requirement: RISK_ASSISTANT 必须注册独立 TaskHandler

TaskHandlerRegistry SHALL 为 AgentType.RISK_ASSISTANT 注册工厂并每次创建新实例。该类型 MUST 不回退为 QA 或 CONTRACT_REVIEW。

#### Scenario: 风控任务选择 handler
- **WHEN** 执行 RISK_ASSISTANT 任务
- **THEN** registry 返回新的 RiskAssessmentTaskHandler

### Requirement: TaskHandler 可选支持暂停和恢复

TaskHandler 模板 SHALL 提供可选 suspended/resume 扩展点。暂停不得调用成功/失败 finalize；恢复 MUST 复用任务和 invocation。未启用该能力的 handler MUST 保持原行为。

#### Scenario: 合同审查不受影响
- **WHEN** CONTRACT_REVIEW handler 完成或失败
- **THEN** 它继续直接 finalize，且无需实现 resume

#### Scenario: 风控暂停
- **WHEN** 风控图 interrupt
- **THEN** handler 持久化 WAITING_REVIEW，不把 invocation 标记成功


## ADDED Requirements

### Requirement: chat 后处理器链可插拔

平台 SHALL 把 chat 流结束后的 Dify 输出归一化与线索收集抽为后处理器链，按 Agent 配置 `config_snapshot.postprocessors`（或等价平台元数据）启用。后处理器 MUST 只消费统一 chunk 累积结果与平台自有归一化输出，不得感知 runtime provider 协议。

后处理器链的顺序、是否执行 MUST 是确定性的，且失败时 MUST 不影响调用记录成功落库；后处理器异常 MUST 被捕获并作为 warning 记录到 `snapshot.runtime`，不得使整次调用从 SUCCEEDED 翻为 FAILED。

#### Scenario: 问答 Agent 默认启用线索收集

- **WHEN** Agent `type` 为问答类，且未显式配置 `config_snapshot.postprocessors`
- **THEN** 平台默认启用线索收集后处理器；`lead_capture_result` 在命中线索时写入 `snapshot.runtime`

#### Scenario: 非问答 Agent 默认不启用线索收集

- **WHEN** Agent `type` 不是问答类，且未显式配置后处理器
- **THEN** 平台默认不运行线索收集后处理器；`snapshot.runtime` 不出现 `lead_capture_result`

#### Scenario: 显式配置覆盖默认

- **WHEN** Agent `config_snapshot.postprocessors` 显式列出要启用的后处理器名
- **THEN** 平台按显式配置执行后处理器链，配置未列出的后处理器不运行

#### Scenario: 后处理器异常不影响调用成功

- **WHEN** 线索收集或其他后处理器抛异常
- **THEN** 调用记录仍按 runtime 实际执行结果落 `SUCCEEDED` 或对应状态；后处理器异常作为 warning 记录到 `snapshot.runtime`，不使调用回滚为 FAILED

### Requirement: 后处理器不得直接依赖 Dify

后处理器实现 MUST 通过平台归一化输出抽象消费最终结果，不得直接 import `app.integrations.dify.*`。Dify 输出归一化（`normalize_dify_final_output` / `NormalizedDifyOutput`）SHALL 封装在问答 handler 或平台归一化层内，对后处理器隐藏 provider 来源。

#### Scenario: 线索后处理器不 import Dify

- **WHEN** 检查线索收集后处理器模块的 import 段
- **THEN** 不出现 `from app.integrations.dify.*`、不出现 `NormalizedDifyOutput` / `normalize_dify_final_output`

#### Scenario: 归一化输出经平台抽象传递

- **WHEN** 后处理器需要访问归一化后的答案文本与 lead_deltas
- **THEN** 通过平台自有的归一化输出类型获取，而非 Dify 专有结构
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.datetime import BeijingDateTime
from app.core.enums import ContractReviewTaskStatus, CounterpartyLevel


class ContractReviewTaskCreate(BaseModel):
    """创建合同审查任务请求。

    Args:
        agent_code: 合同审查 Agent 的稳定 code。默认使用 ``contract-review``。
        file_parse_task_id: 已成功解析的合同文件任务 ID。MVP 后续阶段会要求该任务
            状态为 ``SUCCEEDED``，且归属当前调用主体。
        rule_set_version: 指定规则集版本；为空时使用 Agent 配置中的默认版本。
        callback_metadata: 下游系统自定义追踪字段，只做回显和审计，不参与规则判断。
    """

    agent_code: str = Field(default="contract-review", min_length=1, max_length=100)
    file_parse_task_id: str = Field(min_length=1)
    contract_type: str = Field(default="warehouse", min_length=1, max_length=50)
    counterparty_level: CounterpartyLevel
    rule_set_version: str | None = Field(default=None, max_length=100)
    callback_metadata: dict[str, Any] = Field(default_factory=dict)


class ContractClauseSource(BaseModel):
    """条款来源位置。

    该结构引用 ``ParsedDocumentV1`` 的 section/block 位置，便于人工复核原文。
    """

    section_id: str | None = None
    section_title: str | None = None
    block_id: str | None = None
    page_number: int | None = None
    text_offset: int | None = None


class ContractClauseSourceSpan(BaseModel):
    """条款在解析文本中的高亮 span。"""

    block_id: str
    section_id: str | None = None
    section_title: str | None = None
    start_offset: int
    end_offset: int
    matched_text: str


class ContractClauseReviewResult(BaseModel):
    """单条合同条款判敏结果。

    LLM/Dify 只负责 ``text``、``category``、``source`` 和 ``confidence`` 的抽取
    与分类；``is_sensitive``、``risk_level``、``matched_rules`` 和 ``reason`` 必须
    由 AgentHub 后端规则引擎生成。
    """

    text: str
    category: str
    matrix_clause: str | None = None
    source: ContractClauseSource = Field(default_factory=ContractClauseSource)
    source_block_ids: list[str] = Field(default_factory=list)
    source_spans: list[ContractClauseSourceSpan] = Field(default_factory=list)
    is_sensitive: bool
    risk_level: str
    matched_rules: list[str] = Field(default_factory=list)
    reason: str
    confidence: float = Field(ge=0, le=1)
    warnings: list[dict[str, Any]] = Field(default_factory=list)


class ContractReviewSummary(BaseModel):
    """合同审查摘要。

    Args:
        total_clause_count: 进入规则引擎的条款总数。
        sensitive_clause_count: 被判定为敏感的条款数。
        highest_risk_level: 本次任务最高风险等级。
    """

    total_clause_count: int = 0
    sensitive_clause_count: int = 0
    highest_risk_level: str | None = None
    warning_count: int = 0


class ContractReviewResult(BaseModel):
    """合同审查最终结构化结果。"""

    clauses: list[ContractClauseReviewResult] = Field(default_factory=list)
    summary: ContractReviewSummary = Field(default_factory=ContractReviewSummary)
    warnings: list[dict[str, Any]] = Field(default_factory=list)


class ContractReviewTaskRead(BaseModel):
    """合同审查任务响应。

    首期骨架用于稳定 API 契约。完整实现后，``result`` 在任务成功时返回判敏字典，
    ``error_message`` 在失败时返回稳定错误，``invocation_record_id`` 用于审计追溯。
    """

    model_config = ConfigDict(from_attributes=True)

    id: str
    owner_org_unit_id: str | None = None
    created_by: str | None = None
    api_key_id: str | None = None
    status: ContractReviewTaskStatus
    agent_code: str
    file_parse_task_id: str
    contract_type: str
    counterparty_level: CounterpartyLevel
    rule_set_version: str | None = None
    callback_metadata: dict[str, Any] = Field(default_factory=dict)
    invocation_record_id: str | None = None
    result: ContractReviewResult | None = None
    error_message: str | None = None
    created_at: BeijingDateTime
    updated_at: BeijingDateTime
    finished_at: BeijingDateTime | None = None

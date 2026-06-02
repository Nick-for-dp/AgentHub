from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import EvaluationCaseType, JudgeType, ResourceStatus


class EvaluationCaseCreate(BaseModel):
    agent_id: str
    case_type: EvaluationCaseType = EvaluationCaseType.QA
    input: dict[str, Any] = Field(default_factory=dict)
    expected_output: dict[str, Any] = Field(default_factory=dict)
    reference_context: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)


class EvaluationCaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    agent_id: str
    case_type: EvaluationCaseType
    input: dict[str, Any]
    expected_output: dict[str, Any]
    reference_context: dict[str, Any]
    tags: list[str]
    status: ResourceStatus
    created_at: datetime
    updated_at: datetime


class EvaluationResultCreate(BaseModel):
    agent_id: str
    evaluation_case_id: str | None = None
    invocation_record_id: str | None = None
    score: float | None = None
    judge_type: JudgeType = JudgeType.MANUAL
    judge_model: str | None = None
    comment: str | None = None


class EvaluationResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    agent_id: str
    evaluation_case_id: str | None
    invocation_record_id: str | None
    score: float | None
    judge_type: JudgeType
    judge_model: str | None
    comment: str | None
    created_at: datetime
    updated_at: datetime

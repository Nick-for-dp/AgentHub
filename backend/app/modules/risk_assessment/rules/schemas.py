from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


RULE_SET_VERSION = "risk-rules-v2"


class RuleOutcome(StrEnum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    RESOLVED = "RESOLVED"
    WARNING = "WARNING"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class RuleResult(BaseModel):
    rule_code: str
    version: str = RULE_SET_VERSION
    outcome: RuleOutcome
    input_evidence: list[dict[str, Any]] = Field(default_factory=list)
    message: str
    affected_fields: list[str] = Field(default_factory=list)
    selected_value: Any | None = None

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


ScalarValue = str | int | float | bool


class DocumentType(StrEnum):
    PURCHASE_CONTRACT = "PURCHASE_CONTRACT"
    SALES_CONTRACT = "SALES_CONTRACT"
    APPROVAL_FORM = "APPROVAL_FORM"
    SETTLEMENT_STATEMENT = "SETTLEMENT_STATEMENT"


class FieldStatus(StrEnum):
    FOUND = "FOUND"
    MISSING = "MISSING"
    UNCERTAIN = "UNCERTAIN"


class ExtractedField(BaseModel):
    """单个文档字段的最小稳定结果。"""

    model_config = ConfigDict(extra="forbid")

    field_code: str = Field(min_length=1, max_length=100)
    raw_value: ScalarValue | None = None
    normalized_value: ScalarValue | None = None
    unit: str | None = Field(default=None, max_length=32)
    status: FieldStatus
    sources: list[dict[str, Any]] = Field(default_factory=list)
    alternatives: list[ScalarValue] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_status_contract(self) -> "ExtractedField":
        if self.status == FieldStatus.FOUND:
            if self.raw_value is None and self.normalized_value is None:
                raise ValueError("FOUND field must contain a value")
            if not self.sources:
                raise ValueError("FOUND field must contain at least one source")
        if self.status == FieldStatus.MISSING:
            if self.raw_value is not None or self.normalized_value is not None:
                raise ValueError("MISSING field must not contain a value")
            if self.alternatives:
                raise ValueError("MISSING field must not contain alternatives")
        for source in self.sources:
            if not any(source.get(key) not in (None, "") for key in _SOURCE_KEYS):
                raise ValueError("source must contain block_id, page_number, quote or bbox")
        return self


class DocumentExtractionResult(BaseModel):
    """一期文档抽取的唯一跨模块输出。"""

    model_config = ConfigDict(extra="forbid")

    document_type: DocumentType
    fields: list[ExtractedField]
    warnings: list[str] = Field(default_factory=list)
    parser_version: str = Field(min_length=1, max_length=100)
    extractor_version: str = Field(min_length=1, max_length=100)
    provider_version: str = Field(min_length=1, max_length=100)


_SOURCE_KEYS = ("block_id", "page_number", "quote", "bbox")

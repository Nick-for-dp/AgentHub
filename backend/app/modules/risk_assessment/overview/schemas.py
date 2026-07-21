from enum import StrEnum

from pydantic import BaseModel, Field

from app.core.datetime import BeijingDateTime


class BusinessOverviewDisplayStatus(StrEnum):
    READY = "READY"
    PARTIAL = "PARTIAL"
    MISSING = "MISSING"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class BusinessOverviewRow(BaseModel):
    code: str
    label: str
    content: str
    status: BusinessOverviewDisplayStatus
    source_files: list[str] = Field(default_factory=list)
    field_codes: list[str] = Field(default_factory=list)
    is_human_reviewed: bool = False


class BusinessOverviewProjection(BaseModel):
    business_code: str
    generated_at: BeijingDateTime
    rows: list[BusinessOverviewRow]

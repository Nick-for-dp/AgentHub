from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.datetime import BeijingDateTime
from app.core.enums import (
    DocumentTypeValidationStatus,
    RiskAssessmentTaskStatus,
    RiskReviewTargetKind,
)
from app.modules.risk_assessment.extraction.schemas import DocumentType
from app.modules.risk_assessment.overview.schemas import BusinessOverviewProjection


class RiskAssessmentDocumentCreate(BaseModel):
    file_parse_task_id: str = Field(min_length=1)
    declared_document_type: DocumentType


class RiskAssessmentTaskCreate(BaseModel):
    agent_code: str = Field(default="risk-assistant", min_length=1, max_length=100)
    business_code: str = Field(min_length=1, max_length=100)
    documents: list[RiskAssessmentDocumentCreate] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def reject_duplicate_files(self) -> "RiskAssessmentTaskCreate":
        ids = [item.file_parse_task_id for item in self.documents]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate file_parse_task_id is not allowed")
        return self


class RiskAssessmentDocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    file_parse_task_id: str
    original_filename: str
    declared_document_type: DocumentType
    document_order: int
    type_validation_status: DocumentTypeValidationStatus
    type_validation_warnings: list[str] = Field(default_factory=list)


class RiskReviewSubmit(BaseModel):
    review_item_id: str = Field(min_length=1, max_length=100)
    target_kind: RiskReviewTargetKind
    target_code: str = Field(min_length=1, max_length=100)
    action: str = Field(min_length=1, max_length=50)
    value: Any | None = None
    reason: str = Field(min_length=1, max_length=2000)
    checkpoint_version: int = Field(ge=1)


class RiskReviewEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    review_item_id: str
    target_kind: RiskReviewTargetKind
    target_code: str
    before_value: dict[str, Any] | None = None
    alternatives: list[Any] = Field(default_factory=list)
    after_value: dict[str, Any] | None = None
    action: str
    reason: str
    actor_user_id: str | None = None
    sources: list[dict[str, Any]] = Field(default_factory=list)
    checkpoint_version: int
    created_at: BeijingDateTime


class RiskAssessmentTaskSummaryRead(BaseModel):
    id: str
    business_code: str
    status: RiskAssessmentTaskStatus
    current_node: str | None = None
    document_count: int = 0
    error_message: str | None = None
    created_at: BeijingDateTime
    updated_at: BeijingDateTime
    finished_at: BeijingDateTime | None = None


class RiskAssessmentTaskPageRead(BaseModel):
    items: list[RiskAssessmentTaskSummaryRead]
    total: int
    page: int
    page_size: int


class RiskAssessmentDocumentAccessRead(BaseModel):
    access_url: str
    method: str = "GET"
    headers: dict[str, str] = Field(default_factory=dict)
    expires_seconds: int
    original_filename: str
    file_type: str


class RiskAssessmentTaskRead(BaseModel):
    id: str
    owner_org_unit_id: str | None = None
    created_by: str | None = None
    status: RiskAssessmentTaskStatus
    agent_code: str
    business_code: str
    graph_thread_id: str | None = None
    checkpoint_version: int = 0
    current_node: str | None = None
    invocation_record_id: str | None = None
    versions: dict[str, Any] = Field(default_factory=dict)
    documents: list[RiskAssessmentDocumentRead] = Field(default_factory=list)
    result: dict[str, Any] | None = None
    review_context: dict[str, Any] | None = None
    review_events: list[RiskReviewEventRead] = Field(default_factory=list)
    business_overview: BusinessOverviewProjection | None = None
    error_message: str | None = None
    created_at: BeijingDateTime
    updated_at: BeijingDateTime
    finished_at: BeijingDateTime | None = None

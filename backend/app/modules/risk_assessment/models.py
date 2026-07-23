from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import (
    DocumentTypeValidationStatus,
    RiskAssessmentTaskStatus,
    RiskReviewTargetKind,
)
from app.db.base import Base
from app.db.mixins import IDMixin, TimestampMixin


class RiskAssessmentTask(IDMixin, TimestampMixin, Base):
    __tablename__ = "risk_assessment_task"
    __table_args__ = (
        Index("ix_risk_task_owner_created", "owner_org_unit_id", "created_at"),
        Index("ix_risk_task_created_by_created", "created_by", "created_at"),
        Index("ix_risk_task_status_created", "status", "created_at"),
        Index("ix_risk_task_graph_thread", "graph_thread_id"),
        Index(
            "ix_risk_task_created_by_deleted_created",
            "created_by",
            "deleted_at",
            "created_at",
        ),
    )

    owner_org_unit_id: Mapped[str | None] = mapped_column(
        ForeignKey("org_unit.id"), nullable=True
    )
    created_by: Mapped[str | None] = mapped_column(
        ForeignKey("user_account.id"), nullable=True
    )
    api_key_id: Mapped[str | None] = mapped_column(ForeignKey("api_key.id"), nullable=True)
    agent_code: Mapped[str] = mapped_column(String(100), nullable=False)
    business_code: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=RiskAssessmentTaskStatus.PENDING
    )
    graph_thread_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    current_checkpoint_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    checkpoint_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    current_node: Mapped[str | None] = mapped_column(String(100), nullable=True)
    invocation_record_id: Mapped[str | None] = mapped_column(
        ForeignKey("agent_invocation_record.id"), nullable=True
    )
    versions: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    result_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("user_account.id"), nullable=True
    )


class RiskAssessmentDocument(IDMixin, TimestampMixin, Base):
    __tablename__ = "risk_assessment_document"
    __table_args__ = (
        UniqueConstraint("task_id", "file_parse_task_id", name="uq_risk_document_task_file"),
        Index("ix_risk_document_task_order", "task_id", "document_order"),
        Index("ix_risk_document_file_parse", "file_parse_task_id"),
    )

    task_id: Mapped[str] = mapped_column(
        ForeignKey("risk_assessment_task.id", ondelete="CASCADE"), nullable=False
    )
    file_parse_task_id: Mapped[str] = mapped_column(
        ForeignKey("file_parse_task.id"), nullable=False
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    declared_document_type: Mapped[str] = mapped_column(String(50), nullable=False)
    document_order: Mapped[int] = mapped_column(Integer, nullable=False)
    type_validation_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=DocumentTypeValidationStatus.UNVERIFIED
    )
    type_validation_warnings: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    extraction_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class RiskReviewEvent(IDMixin, TimestampMixin, Base):
    __tablename__ = "risk_review_event"
    __table_args__ = (
        Index("ix_risk_review_task_created", "task_id", "created_at"),
        Index("ix_risk_review_actor_created", "actor_user_id", "created_at"),
    )

    task_id: Mapped[str] = mapped_column(
        ForeignKey("risk_assessment_task.id", ondelete="CASCADE"), nullable=False
    )
    review_item_id: Mapped[str] = mapped_column(String(100), nullable=False)
    target_kind: Mapped[str] = mapped_column(
        String(32), nullable=False, default=RiskReviewTargetKind.FIELD
    )
    target_code: Mapped[str] = mapped_column(String(100), nullable=False)
    before_value: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    alternatives: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    after_value: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    actor_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("user_account.id"), nullable=True
    )
    sources: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    checkpoint_version: Mapped[int] = mapped_column(Integer, nullable=False)

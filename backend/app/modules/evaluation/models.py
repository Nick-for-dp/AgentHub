from sqlalchemy import ForeignKey, Index, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import EvaluationCaseType, JudgeType, ResourceStatus
from app.db.base import Base
from app.db.mixins import IDMixin, TimestampMixin


class EvaluationCase(IDMixin, TimestampMixin, Base):
    __tablename__ = "evaluation_case"
    __table_args__ = (Index("ix_evaluation_case_agent", "agent_id"),)

    agent_id: Mapped[str] = mapped_column(ForeignKey("agent.id"), nullable=False)
    case_type: Mapped[str] = mapped_column(String(50), nullable=False, default=EvaluationCaseType.QA)
    input: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    expected_output: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    reference_context: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    tags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=ResourceStatus.ACTIVE)


class EvaluationResult(IDMixin, TimestampMixin, Base):
    __tablename__ = "evaluation_result"
    __table_args__ = (
        Index("ix_evaluation_result_agent", "agent_id"),
        Index("ix_evaluation_result_case", "evaluation_case_id"),
        Index("ix_evaluation_result_invocation", "invocation_record_id"),
    )

    agent_id: Mapped[str] = mapped_column(ForeignKey("agent.id"), nullable=False)
    evaluation_case_id: Mapped[str | None] = mapped_column(ForeignKey("evaluation_case.id"), nullable=True)
    invocation_record_id: Mapped[str | None] = mapped_column(
        ForeignKey("agent_invocation_record.id"),
        nullable=True,
    )
    score: Mapped[float | None] = mapped_column(nullable=True)
    judge_type: Mapped[str] = mapped_column(String(50), nullable=False, default=JudgeType.MANUAL)
    judge_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

from sqlalchemy import ForeignKey, Index, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import IDMixin, TimestampMixin


class RiskGraphCheckpoint(IDMixin, TimestampMixin, Base):
    __tablename__ = "risk_graph_checkpoint"
    __table_args__ = (
        UniqueConstraint("thread_id", "version", name="uq_risk_checkpoint_thread_version"),
        UniqueConstraint("checkpoint_id", name="uq_risk_checkpoint_id"),
        Index("ix_risk_checkpoint_task_version", "task_id", "version"),
        Index("ix_risk_checkpoint_thread_version", "thread_id", "version"),
    )

    task_id: Mapped[str] = mapped_column(
        ForeignKey("risk_assessment_task.id", ondelete="CASCADE"), nullable=False
    )
    thread_id: Mapped[str] = mapped_column(String(100), nullable=False)
    checkpoint_id: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    next_node: Mapped[str | None] = mapped_column(String(100), nullable=True)

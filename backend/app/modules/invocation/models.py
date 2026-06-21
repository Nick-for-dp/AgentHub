from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import CallerType, InvocationStatus, OperationType
from app.db.base import Base
from app.db.mixins import IDMixin, utcnow


class AgentInvocationRecord(IDMixin, Base):
    __tablename__ = "agent_invocation_record"
    __table_args__ = (
        Index("ix_invocation_request_id", "request_id"),
        Index("ix_invocation_agent_created", "agent_id", "created_at"),
        Index("ix_invocation_org_created", "org_unit_id", "created_at"),
        Index("ix_invocation_api_key_created", "api_key_id", "created_at"),
    )

    request_id: Mapped[str] = mapped_column(String(64), nullable=False)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agent.id"), nullable=False)
    org_unit_id: Mapped[str | None] = mapped_column(ForeignKey("org_unit.id"), nullable=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("user_account.id"), nullable=True)
    api_key_id: Mapped[str | None] = mapped_column(ForeignKey("api_key.id"), nullable=True)
    caller_type: Mapped[str] = mapped_column(String(32), nullable=False, default=CallerType.API_KEY)
    source_channel: Mapped[str | None] = mapped_column(String(50), nullable=True)
    operation_type: Mapped[str] = mapped_column(String(50), nullable=False, default=OperationType.QA)
    input: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    output: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    stream_mode: Mapped[bool] = mapped_column(nullable=False, default=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=InvocationStatus.PENDING)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_usage: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    latency_ms: Mapped[int | None] = mapped_column(nullable=True)
    # 合并后的运行时快照，内部固定保留 retrieval / model / runtime 三个顶层子键，
    # 便于审计与前端按维度读取检索、模型、运行时（含 node_trace、dify_metadata 等）信息
    snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    session_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import (
    ConversationMessageRole,
    ConversationMessageStatus,
    ConversationStatus,
    ProviderType,
)
from app.db.base import Base
from app.db.mixins import IDMixin, TimestampMixin, utcnow


class Conversation(IDMixin, TimestampMixin, Base):
    __tablename__ = "conversation"
    __table_args__ = (
        Index("ix_conversation_user_last_message", "user_id", "last_message_at"),
        Index("ix_conversation_user_status_last_message", "user_id", "status", "last_message_at"),
        Index("ix_conversation_agent_user", "agent_id", "user_id"),
    )

    agent_id: Mapped[str] = mapped_column(ForeignKey("agent.id"), nullable=False)
    agent_code: Mapped[str] = mapped_column(String(100), nullable=False)
    user_id: Mapped[str] = mapped_column(ForeignKey("user_account.id"), nullable=False)
    org_unit_id: Mapped[str | None] = mapped_column(ForeignKey("org_unit.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False, default=ProviderType.DIFY)
    provider_conversation_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=ConversationStatus.ACTIVE)
    last_message_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class ConversationMessage(IDMixin, Base):
    __tablename__ = "conversation_message"
    __table_args__ = (
        Index("ix_conversation_message_conversation_sequence", "conversation_id", "sequence_no"),
        Index("ix_conversation_message_conversation_created", "conversation_id", "created_at"),
    )

    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversation.id"), nullable=False)
    sequence_no: Mapped[int] = mapped_column(nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default=ConversationMessageRole.USER)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    thought: Mapped[str | None] = mapped_column(Text, nullable=True)
    steps: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    provider_message_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    invocation_record_id: Mapped[str | None] = mapped_column(
        ForeignKey("agent_invocation_record.id"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=ConversationMessageStatus.COMPLETED,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )

    conversation: Mapped[Conversation] = relationship()

from sqlalchemy import ForeignKey, Index, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import AgentType, PublishStatus, ResourceStatus, RuntimeType, Visibility
from app.db.base import Base
from app.db.mixins import IDMixin, TimestampMixin
from app.modules.knowledge.models import KnowledgeBase


class Agent(IDMixin, TimestampMixin, Base):
    __tablename__ = "agent"
    __table_args__ = (
        UniqueConstraint("code", name="uq_agent_code"),
        Index("ix_agent_owner", "owner_org_unit_id"),
    )

    code: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False, default=AgentType.QA)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner_org_unit_id: Mapped[str] = mapped_column(ForeignKey("org_unit.id"), nullable=False)
    runtime_type: Mapped[str] = mapped_column(String(50), nullable=False, default=RuntimeType.DIFY)
    runtime_app_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    version: Mapped[int] = mapped_column(nullable=False, default=1)
    publish_status: Mapped[str] = mapped_column(String(32), nullable=False, default=PublishStatus.DRAFT)
    visibility: Mapped[str] = mapped_column(String(32), nullable=False, default=Visibility.EXTERNAL)
    config_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("user_account.id"), nullable=True)


class AgentKnowledgeBase(IDMixin, TimestampMixin, Base):
    __tablename__ = "agent_knowledge_base"
    __table_args__ = (
        UniqueConstraint("agent_id", "knowledge_base_id", name="uq_agent_knowledge_base"),
        Index("ix_agent_kb_agent", "agent_id"),
        Index("ix_agent_kb_kb", "knowledge_base_id"),
    )

    agent_id: Mapped[str] = mapped_column(ForeignKey("agent.id"), nullable=False)
    knowledge_base_id: Mapped[str] = mapped_column(ForeignKey("knowledge_base.id"), nullable=False)
    priority: Mapped[int] = mapped_column(nullable=False, default=100)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=ResourceStatus.ACTIVE)

    agent: Mapped[Agent] = relationship()
    knowledge_base: Mapped["KnowledgeBase"] = relationship()

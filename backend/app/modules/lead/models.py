from sqlalchemy import ForeignKey, Index, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import LeadCaptureEventStatus, LeadStatus
from app.db.base import Base
from app.db.mixins import IDMixin, TimestampMixin


class LeadContact(IDMixin, TimestampMixin, Base):
    __tablename__ = "lead_contact"
    __table_args__ = (
        UniqueConstraint("phone_normalized", name="uq_lead_contact_phone_normalized"),
        Index("ix_lead_contact_user", "user_id"),
        Index("ix_lead_contact_org", "org_unit_id"),
    )

    user_id: Mapped[str | None] = mapped_column(ForeignKey("user_account.id"), nullable=True)
    org_unit_id: Mapped[str | None] = mapped_column(ForeignKey("org_unit.id"), nullable=True)
    customer_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    company_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    contact_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    contact_value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone_normalized: Mapped[str | None] = mapped_column(String(32), nullable=True)


class SalesLead(IDMixin, TimestampMixin, Base):
    __tablename__ = "sales_lead"
    __table_args__ = (
        Index("ix_sales_lead_conversation", "conversation_id"),
        Index("ix_sales_lead_user_agent_status", "user_id", "agent_id", "status"),
        Index("ix_sales_lead_contact", "contact_id"),
    )

    contact_id: Mapped[str | None] = mapped_column(ForeignKey("lead_contact.id"), nullable=True)
    conversation_id: Mapped[str | None] = mapped_column(ForeignKey("conversation.id"), nullable=True)
    agent_id: Mapped[str | None] = mapped_column(ForeignKey("agent.id"), nullable=True)
    agent_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("user_account.id"), nullable=True)
    org_unit_id: Mapped[str | None] = mapped_column(ForeignKey("org_unit.id"), nullable=True)
    requirement_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    requirement_types: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    region: Mapped[str | None] = mapped_column(String(100), nullable=True)
    missing_fields: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=LeadStatus.PROVISIONAL)

    contact: Mapped[LeadContact | None] = relationship()


class LeadCaptureEvent(IDMixin, TimestampMixin, Base):
    __tablename__ = "lead_capture_event"
    __table_args__ = (
        Index("ix_lead_capture_event_invocation", "invocation_record_id"),
        Index("ix_lead_capture_event_conversation", "conversation_id"),
        Index("ix_lead_capture_event_lead", "sales_lead_id"),
    )

    conversation_id: Mapped[str | None] = mapped_column(ForeignKey("conversation.id"), nullable=True)
    conversation_message_id: Mapped[str | None] = mapped_column(ForeignKey("conversation_message.id"), nullable=True)
    invocation_record_id: Mapped[str | None] = mapped_column(
        ForeignKey("agent_invocation_record.id"),
        nullable=True,
    )
    sales_lead_id: Mapped[str | None] = mapped_column(ForeignKey("sales_lead.id"), nullable=True)
    contact_id: Mapped[str | None] = mapped_column(ForeignKey("lead_contact.id"), nullable=True)
    agent_id: Mapped[str | None] = mapped_column(ForeignKey("agent.id"), nullable=True)
    agent_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("user_account.id"), nullable=True)
    org_unit_id: Mapped[str | None] = mapped_column(ForeignKey("org_unit.id"), nullable=True)
    raw_delta: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    normalized_delta: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    followup_decision: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    action: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=LeadCaptureEventStatus.IGNORED)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

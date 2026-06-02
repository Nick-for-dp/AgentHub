from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.integrations.dify.output import NormalizedDifyOutput
from app.modules.agent.models import Agent
from app.modules.conversation.models import Conversation, ConversationMessage


class LeadDelta(BaseModel):
    target_lead_id: str | None = None
    action: str = "ignore"
    requirement_summary: str | None = None
    requirement_types: list[str] = Field(default_factory=list)
    region: str | None = None
    contact_type: str | None = None
    contact_value: str | None = None
    customer_name: str | None = None
    company_name: str | None = None
    missing_fields: list[str] = Field(default_factory=list)
    should_capture: bool = False
    evidence: str = ""
    confidence: float = 0.0
    reason: str = ""


class LeadCaptureContext(BaseModel):
    agent_id: str | None = None
    agent_code: str | None = None
    user_id: str | None = None
    org_unit_id: str | None = None
    conversation_id: str | None = None
    conversation_message_id: str | None = None
    invocation_record_id: str | None = None

    @classmethod
    def from_chat(
        cls,
        *,
        agent: Agent,
        user_id: str | None,
        org_unit_id: str | None,
        conversation: Conversation | None,
        assistant_message: ConversationMessage | None,
        invocation_record_id: str | None,
    ) -> "LeadCaptureContext":
        return cls(
            agent_id=agent.id,
            agent_code=agent.code,
            user_id=user_id,
            org_unit_id=org_unit_id,
            conversation_id=conversation.id if conversation else None,
            conversation_message_id=assistant_message.id if assistant_message else None,
            invocation_record_id=invocation_record_id,
        )


class LeadCaptureResult(BaseModel):
    captured_count: int = 0
    ignored_count: int = 0
    failed_count: int = 0
    lead_ids: list[str] = Field(default_factory=list)
    contact_ids: list[str] = Field(default_factory=list)
    events: list[dict[str, Any]] = Field(default_factory=list)


class LeadOutputCapture(BaseModel):
    output: NormalizedDifyOutput
    context: LeadCaptureContext


class LeadCaptureEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    conversation_id: str | None
    conversation_message_id: str | None
    invocation_record_id: str | None
    sales_lead_id: str | None
    contact_id: str | None
    action: str | None
    status: str
    reason: str | None
    raw_delta: dict[str, Any]
    normalized_delta: dict[str, Any]
    followup_decision: dict[str, Any]
    created_at: datetime


class SalesLeadRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    contact_id: str | None
    conversation_id: str | None
    agent_id: str | None
    agent_code: str | None
    agent_name: str | None = None
    user_id: str | None
    org_unit_id: str | None
    org_unit_name: str | None = None
    customer_name: str | None = None
    company_name: str | None = None
    contact_type: str | None = None
    contact_value: str | None = None
    phone_normalized: str | None = None
    requirement_summary: str | None
    requirement_types: list[str]
    region: str | None
    missing_fields: list[str]
    status: str
    has_contact: bool = False
    event_count: int = 0
    latest_event: LeadCaptureEventRead | None = None
    created_at: datetime
    updated_at: datetime


class SalesLeadPage(BaseModel):
    items: list[SalesLeadRead]
    total: int
    page: int
    page_size: int

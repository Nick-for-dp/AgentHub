from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import (
    ConversationMessageRole,
    ConversationMessageStatus,
    ConversationStatus,
    ProviderType,
)


class ConversationCreate(BaseModel):
    agent_id: str
    agent_code: str
    user_id: str
    org_unit_id: str | None = None
    title: str = Field(default="新对话", max_length=200)
    provider: ProviderType = ProviderType.DIFY


class ConversationUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    status: ConversationStatus | None = None


class ConversationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    agent_id: str
    agent_code: str
    user_id: str
    org_unit_id: str | None
    title: str
    provider: ProviderType
    provider_conversation_id: str | None
    status: ConversationStatus
    last_message_at: datetime
    created_at: datetime
    updated_at: datetime


class ConversationMessageCreate(BaseModel):
    conversation_id: str
    role: ConversationMessageRole
    content: str = ""
    thought: str | None = None
    steps: list[dict[str, Any]] = Field(default_factory=list)
    provider_message_id: str | None = None
    invocation_record_id: str | None = None
    status: ConversationMessageStatus = ConversationMessageStatus.COMPLETED


class ConversationMessageUpdate(BaseModel):
    content: str | None = None
    thought: str | None = None
    steps: list[dict[str, Any]] | None = None
    provider_message_id: str | None = None
    invocation_record_id: str | None = None
    status: ConversationMessageStatus | None = None


class ConversationMessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    conversation_id: str
    sequence_no: int
    role: ConversationMessageRole
    content: str
    thought: str | None
    steps: list[dict[str, Any]]
    provider_message_id: str | None
    invocation_record_id: str | None
    status: ConversationMessageStatus
    created_at: datetime
    updated_at: datetime


class ConversationWithMessages(BaseModel):
    conversation: ConversationRead | None = None
    messages: list[ConversationMessageRead] = Field(default_factory=list)


class ConversationPage(BaseModel):
    items: list[ConversationRead]
    total: int
    page: int
    page_size: int

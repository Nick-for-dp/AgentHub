from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.datetime import BeijingDateTime
from app.core.enums import (
    APIKeyOwnerType,
    APIKeyStatus,
    PolicyEffect,
    ResourceStatus,
    ResourceType,
    SubjectType,
)


class APIKeyCreateByPhone(BaseModel):
    phone: str = Field(min_length=1)
    name: str = Field(min_length=1, max_length=100)
    scopes: list[str] = Field(default_factory=list)
    expires_at: datetime | None = None

    @field_validator("phone")
    @classmethod
    def strip_phone(cls, value: str) -> str:
        return value.strip()


class APIKeyCreate(BaseModel):
    owner_type: APIKeyOwnerType
    owner_id: str
    name: str = Field(min_length=1, max_length=100)
    scopes: list[str] = Field(default_factory=list)
    expires_at: datetime | None = None


class APIKeyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    key_prefix: str
    owner_type: APIKeyOwnerType
    owner_id: str
    issued_for_phone: str | None
    name: str
    scopes: list[str]
    status: APIKeyStatus
    expires_at: BeijingDateTime | None
    last_used_at: BeijingDateTime | None
    created_at: BeijingDateTime
    updated_at: BeijingDateTime


class APIKeyIssued(BaseModel):
    api_key: str
    record: APIKeyRead


class PermissionPolicyCreate(BaseModel):
    subject_type: SubjectType
    subject_id: str
    resource_type: ResourceType
    resource_id: str
    actions: list[str] = Field(min_length=1)
    effect: PolicyEffect = PolicyEffect.ALLOW


class PermissionPolicyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    subject_type: SubjectType
    subject_id: str
    resource_type: ResourceType
    resource_id: str
    actions: list[str]
    effect: PolicyEffect
    status: ResourceStatus
    created_at: BeijingDateTime
    updated_at: BeijingDateTime


class AuthenticatedSubject(BaseModel):
    caller_type: str
    user_id: str | None = None
    org_unit_id: str | None = None
    api_key_id: str | None = None
    embed_session_id: str | None = None
    embed_agent_code: str | None = None
    scopes: list[str] = Field(default_factory=list)


# ── 登录认证 ──────────────────────────────────────────────────


class LoginRequest(BaseModel):
    phone: str = Field(min_length=1)
    password: str = Field(min_length=1)


class UserSummary(BaseModel):
    """不包含密码、token_version 等敏感字段的用户摘要。"""
    id: str
    name: str
    phone: str | None
    org_unit_id: str
    org_unit_name: str | None = None
    is_admin: bool = False


class SessionResponse(BaseModel):
    user: UserSummary
    access_expires_at: BeijingDateTime
    idle_expires_at: BeijingDateTime
    expires_in: int
    idle_expires_in: int


class SessionStatusResponse(BaseModel):
    authenticated: bool
    user: UserSummary | None = None
    access_expires_at: BeijingDateTime | None = None
    idle_expires_at: BeijingDateTime | None = None
    expires_in: int = 0
    idle_expires_in: int = 0


# ── 官网嵌入认证 ──────────────────────────────────────────────


class EmbedExchangeRequest(BaseModel):
    token: str = Field(min_length=1)
    agent_code: str = Field(default="qa", min_length=1, max_length=100)

    @field_validator("token", "agent_code")
    @classmethod
    def strip_embed_fields(cls, value: str) -> str:
        return value.strip()


class EmbedExchangeResponse(BaseModel):
    authenticated: bool = True
    expires_in: int


class EmbedSessionUser(BaseModel):
    id: str
    phone: str | None = None


class EmbedSessionStatusResponse(BaseModel):
    authenticated: bool
    user: EmbedSessionUser | None = None
    agent_code: str | None = None
    expires_in: int = 0

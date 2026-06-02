from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

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
    expires_at: datetime | None
    last_used_at: datetime | None
    created_at: datetime
    updated_at: datetime


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
    created_at: datetime
    updated_at: datetime


class AuthenticatedSubject(BaseModel):
    caller_type: str
    user_id: str | None = None
    org_unit_id: str | None = None
    api_key_id: str | None = None
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


class SessionResponse(BaseModel):
    user: UserSummary
    access_expires_at: datetime
    idle_expires_at: datetime
    expires_in: int
    idle_expires_in: int


class SessionStatusResponse(BaseModel):
    authenticated: bool
    user: UserSummary | None = None
    access_expires_at: datetime | None = None
    idle_expires_at: datetime | None = None
    expires_in: int = 0
    idle_expires_in: int = 0

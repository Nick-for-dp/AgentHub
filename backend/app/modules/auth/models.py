from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import (
    APIKeyOwnerType,
    APIKeyStatus,
    EmbedSessionStatus,
    PolicyEffect,
    ResourceStatus,
    ResourceType,
    SubjectType,
)
from app.db.base import Base
from app.db.mixins import IDMixin, TimestampMixin, utcnow


class AuthSession(IDMixin, TimestampMixin, Base):
    __tablename__ = "auth_session"
    __table_args__ = (
        Index("ix_auth_session_user", "user_id"),
        Index("ix_auth_session_idle_expires", "idle_expires_at"),
        Index("ix_auth_session_revoked", "revoked_at"),
    )

    session_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("user_account.id"), nullable=False)
    phone_normalized: Mapped[str | None] = mapped_column(String(32), nullable=True)
    token_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    access_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    idle_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    user_agent_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    client_ip_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)


class EmbedSession(IDMixin, Base):
    __tablename__ = "embed_session"
    __table_args__ = (
        Index("ix_embed_session_hash", "session_hash"),
        Index("ix_embed_session_external_user", "external_user_id"),
        Index("ix_embed_session_user", "user_id"),
        Index("ix_embed_session_agent_code", "agent_code"),
        Index("ix_embed_session_status", "status"),
        Index("ix_embed_session_expires_at", "expires_at"),
    )

    session_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    external_user_id: Mapped[str] = mapped_column(String(100), nullable=False)
    phone_normalized: Mapped[str | None] = mapped_column(String(32), nullable=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("user_account.id"), nullable=False)
    agent_code: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=EmbedSessionStatus.ACTIVE)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class APIKey(IDMixin, TimestampMixin, Base):
    __tablename__ = "api_key"
    __table_args__ = (
        Index("ix_api_key_key_prefix", "key_prefix"),
        Index("ix_api_key_owner", "owner_type", "owner_id"),
        Index("ix_api_key_issued_for_phone", "issued_for_phone"),
    )

    key_prefix: Mapped[str] = mapped_column(String(32), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    owner_type: Mapped[str] = mapped_column(String(32), nullable=False, default=APIKeyOwnerType.USER)
    owner_id: Mapped[str] = mapped_column(String(36), nullable=False)
    issued_for_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    scopes: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=APIKeyStatus.ACTIVE)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)


class PermissionPolicy(IDMixin, TimestampMixin, Base):
    __tablename__ = "permission_policy"
    __table_args__ = (
        Index("ix_permission_subject", "subject_type", "subject_id"),
        Index("ix_permission_resource", "resource_type", "resource_id"),
    )

    subject_type: Mapped[str] = mapped_column(String(32), nullable=False, default=SubjectType.USER)
    subject_id: Mapped[str] = mapped_column(String(36), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False, default=ResourceType.AGENT)
    resource_id: Mapped[str] = mapped_column(String(36), nullable=False)
    actions: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    effect: Mapped[str] = mapped_column(String(16), nullable=False, default=PolicyEffect.ALLOW)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=ResourceStatus.ACTIVE)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("user_account.id"), nullable=True)

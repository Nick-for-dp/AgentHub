from sqlalchemy import ForeignKey, Index, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import ParseStatus, ProviderType, ResourceStatus
from app.db.base import Base
from app.db.mixins import IDMixin, TimestampMixin


class KnowledgeBase(IDMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_base"
    __table_args__ = (
        Index("ix_knowledge_base_owner", "owner_org_unit_id"),
        Index("ix_knowledge_base_provider_kb", "provider", "provider_kb_id"),
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    owner_org_unit_id: Mapped[str] = mapped_column(ForeignKey("org_unit.id"), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False, default=ProviderType.DIFY)
    provider_kb_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(200), nullable=True)
    retrieval_config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=ResourceStatus.ACTIVE)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("user_account.id"), nullable=True)


class Document(IDMixin, TimestampMixin, Base):
    __tablename__ = "document"
    __table_args__ = (
        Index("ix_document_kb", "knowledge_base_id"),
        Index("ix_document_provider_doc", "provider_doc_id"),
    )

    knowledge_base_id: Mapped[str] = mapped_column(ForeignKey("knowledge_base.id"), nullable=False)
    owner_org_unit_id: Mapped[str] = mapped_column(ForeignKey("org_unit.id"), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    file_size: Mapped[int | None] = mapped_column(nullable=True)
    storage_uri: Mapped[str | None] = mapped_column(String(500), nullable=True)
    provider_doc_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    parse_status: Mapped[str] = mapped_column(String(32), nullable=False, default=ParseStatus.PENDING)
    parser_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(200), nullable=True)
    chunk_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    failed_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("user_account.id"), nullable=True)

    knowledge_base: Mapped[KnowledgeBase] = relationship()

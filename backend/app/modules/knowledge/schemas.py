from app.core.datetime import BeijingDateTime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import ParseStatus, ProviderType, ResourceStatus


class KnowledgeBaseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    owner_org_unit_id: str
    provider: ProviderType = ProviderType.DIFY
    provider_kb_id: str | None = None
    embedding_model: str | None = None
    retrieval_config: dict[str, Any] = Field(default_factory=dict)


class KnowledgeBaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    owner_org_unit_id: str
    provider: ProviderType
    provider_kb_id: str | None
    embedding_model: str | None
    retrieval_config: dict[str, Any]
    status: ResourceStatus
    created_by: str | None
    created_at: BeijingDateTime
    updated_at: BeijingDateTime


class DocumentCreate(BaseModel):
    knowledge_base_id: str
    owner_org_unit_id: str
    file_name: str = Field(min_length=1, max_length=255)
    file_type: str | None = None
    file_size: int | None = Field(default=None, ge=0)
    storage_uri: str | None = None
    provider_doc_id: str | None = None
    parser_version: str | None = None
    embedding_model: str | None = None
    chunk_version: str | None = None


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    knowledge_base_id: str
    owner_org_unit_id: str
    file_name: str
    file_type: str | None
    file_size: int | None
    storage_uri: str | None
    provider_doc_id: str | None
    parse_status: ParseStatus
    parser_version: str | None
    embedding_model: str | None
    chunk_version: str | None
    failed_reason: str | None
    created_by: str | None
    created_at: BeijingDateTime
    updated_at: BeijingDateTime

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from app.core.datetime import BeijingDateTime
from app.core.enums import AgentType, PublishStatus, RuntimeType, Visibility
from app.core.security import sanitize_dict_for_log


class AgentCreate(BaseModel):
    code: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    type: AgentType = AgentType.QA
    description: str | None = None
    owner_org_unit_id: str
    runtime_type: RuntimeType = RuntimeType.DIFY
    runtime_app_id: str | None = None
    visibility: Visibility = Visibility.EXTERNAL
    config_snapshot: dict[str, Any] = Field(default_factory=dict)


class AgentUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    description: str | None = None
    runtime_type: RuntimeType | None = None
    runtime_app_id: str | None = None
    publish_status: PublishStatus | None = None
    visibility: Visibility | None = None
    config_snapshot: dict[str, Any] | None = None


class AgentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    code: str
    name: str
    type: AgentType
    description: str | None
    owner_org_unit_id: str
    runtime_type: RuntimeType
    runtime_app_id: str | None
    version: int
    publish_status: PublishStatus
    visibility: Visibility
    config_snapshot: dict[str, Any]
    created_by: str | None
    created_at: BeijingDateTime
    updated_at: BeijingDateTime

    @field_serializer("config_snapshot")
    @classmethod
    def sanitize_config_snapshot(cls, value: dict[str, Any]) -> dict[str, Any]:
        """API 响应序列化时自动脱敏 config_snapshot 中的敏感字段。

        注意：这里脱敏的是 API 输出给客户端的 JSON 响应，
        不影响运行时内部使用 config_snapshot 的原始值。
        运行时传给 Dify 的 inputs 由 AgentRuntimeService 另外过滤。
        """
        if not value:
            return value
        return sanitize_dict_for_log(value)


class AgentKnowledgeBaseBind(BaseModel):
    knowledge_base_id: str
    priority: int = 100


class AgentKnowledgeBaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    agent_id: str
    knowledge_base_id: str
    priority: int
    status: str
    created_at: BeijingDateTime

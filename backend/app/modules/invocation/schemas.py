"""
调用记录 (agent_invocation_record) 的 Pydantic Schema。

调用记录是平台审计的核心数据源，同时承载业务视角（"用户问了什么、AI 答了什么"）
和技术视角（"哪个 runtime 被调用、耗时多少、是否报错"）。

MVP 将 qa_record 和 invocation_log 合并到此表，避免数据冗余。
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.datetime import BeijingDateTime
from app.core.enums import CallerType, InvocationStatus, OperationType


class InvocationRecordCreate(BaseModel):
    """创建调用记录（在 Agent 调用开始时写库）。

    此时仅有输入信息，输出/状态/耗时等字段在调用结束后通过 finish 更新。
    """
    request_id: str
    agent_id: str
    org_unit_id: str | None = None
    user_id: str | None = None
    api_key_id: str | None = None
    caller_type: CallerType = CallerType.API_KEY
    source_channel: str | None = None
    operation_type: OperationType = OperationType.QA
    input: dict[str, Any] = Field(default_factory=dict)
    stream_mode: bool = True
    session_id: str | None = None


class InvocationRecordFinish(BaseModel):
    """更新调用记录（在 Agent 调用结束时写库）。

    填充输出内容、最终状态、耗时、错误信息、运行时快照等。
    """
    output: dict[str, Any] = Field(default_factory=dict)
    status: InvocationStatus = InvocationStatus.SUCCEEDED
    error_code: str | None = None
    error_message: str | None = None
    token_usage: dict[str, Any] = Field(default_factory=dict)
    latency_ms: int | None = None
    # 固定结构 {"retrieval": {...}, "model": {...}, "runtime": {...}}
    snapshot: dict[str, Any] = Field(default_factory=dict)


class InvocationRecordFilter(BaseModel):
    """调用记录查询筛选条件。

    所有字段均为可选，不填则不筛选。
    管理端可按 Agent、状态、时间范围、API Key 等维度筛选调用记录。
    """
    agent_id: str | None = None
    agent_code: str | None = None
    status: InvocationStatus | None = None
    api_key_id: str | None = None
    created_from: datetime | None = None
    created_to: datetime | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class InvocationRecordRead(BaseModel):
    """调用记录 API 响应。

    包含调用记录的完整信息，用于管理端列表和详情展示。
    """
    model_config = ConfigDict(from_attributes=True)

    id: str
    request_id: str
    agent_id: str
    agent_code: str | None = None
    agent_name: str | None = None
    org_unit_id: str | None
    org_unit_name: str | None = None
    user_id: str | None
    customer_name: str | None = None
    customer_phone: str | None = None
    api_key_id: str | None
    api_key_name: str | None = None
    api_key_prefix: str | None = None
    caller_type: CallerType
    source_channel: str | None
    operation_type: OperationType
    input: dict[str, Any]
    output: dict[str, Any]
    stream_mode: bool
    status: InvocationStatus
    error_code: str | None
    error_message: str | None
    token_usage: dict[str, Any]
    latency_ms: int | None
    snapshot: dict[str, Any]
    session_id: str | None
    created_at: BeijingDateTime
    finished_at: BeijingDateTime | None


class InvocationRecordPage(BaseModel):
    """分页查询结果。

    items: 当前页记录列表
    total: 符合筛选条件的总记录数（用于前端分页器显示"共 X 条"）
    page: 当前页码
    page_size: 每页条数
    """
    items: list[InvocationRecordRead]
    total: int
    page: int
    page_size: int

"""Analytics Pydantic schemas — 只读统计指标的请求/响应模型。"""

from app.core.datetime import BeijingDateTime

from pydantic import BaseModel, Field


class DAUItem(BaseModel):
    """单日活跃用户数。"""
    date: str
    active_users: int


class UserMessageCountItem(BaseModel):
    """用户消息发送次数排行条目。"""
    user_id: str
    user_name: str | None = None
    phone_normalized: str | None = None
    org_unit_name: str | None = None
    message_count: int
    last_message_at: BeijingDateTime | None = None
    agent_codes: list[str] = Field(default_factory=list)


class UserMessageCountPage(BaseModel):
    items: list[UserMessageCountItem]
    total: int
    page: int
    page_size: int


class UserChatDurationItem(BaseModel):
    """用户单日聊天活跃跨度条目（根据聊天消息时间估算）。"""
    user_id: str
    user_name: str | None = None
    chat_date: str
    first_message_at: BeijingDateTime | None = None
    last_message_at: BeijingDateTime | None = None
    duration_seconds: int
    message_count: int


class UserChatDurationPage(BaseModel):
    items: list[UserChatDurationItem]
    total: int
    page: int
    page_size: int


class AgentBusinessFollowupItem(BaseModel):
    """智能体业务追问次数统计条目。"""
    agent_code: str | None = None
    agent_name: str | None = None
    followup_count: int


class AgentBusinessFollowupPage(BaseModel):
    items: list[AgentBusinessFollowupItem]
    total: int
    page: int
    page_size: int

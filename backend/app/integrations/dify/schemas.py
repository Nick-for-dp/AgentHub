from typing import Any

from pydantic import BaseModel, Field


class DifyChatRequest(BaseModel):
    query: str
    user: str
    inputs: dict[str, Any] = Field(default_factory=dict)
    conversation_id: str | None = None
    response_mode: str = "streaming"


class DifyChatChunk(BaseModel):
    event: str
    answer: str | None = None
    thought: str | None = None
    conversation_id: str | None = None
    message_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    # Dify workflow 节点事件数据（含 node_retry 重试状态）
    node: dict[str, Any] | None = None
    # Dify workflow_finished 的完整 outputs，用于解析 text / lead_deltas / followup_decision
    workflow_outputs: dict[str, Any] | None = None
    # Dify 顶层 error 事件消息（workflow 执行失败时由 Dify 发送）
    error: str | None = None

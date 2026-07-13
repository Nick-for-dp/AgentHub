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


class DifyWorkflowRunRequest(BaseModel):
    inputs: dict[str, Any] = Field(default_factory=dict)
    user: str
    response_mode: str = "blocking"


class DifyWorkflowRunResult(BaseModel):
    raw: dict[str, Any] = Field(default_factory=dict)
    workflow_run_id: str | None = None
    task_id: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    outputs: dict[str, Any] = Field(default_factory=dict)
    status: str | None = None
    error: str | None = None
    elapsed_time: float | None = None
    total_tokens: int | None = None

    @classmethod
    def from_response(cls, payload: dict[str, Any]) -> "DifyWorkflowRunResult":
        """从 Dify workflow blocking 响应中提取常用审计字段。"""
        data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        outputs = data.get("outputs") if isinstance(data.get("outputs"), dict) else {}
        total_tokens = data.get("total_tokens")
        return cls(
            raw=payload,
            workflow_run_id=_optional_string(payload.get("workflow_run_id") or data.get("id")),
            task_id=_optional_string(payload.get("task_id")),
            data=data,
            outputs=outputs,
            status=_optional_string(data.get("status")),
            error=_optional_string(data.get("error")),
            elapsed_time=_optional_float(data.get("elapsed_time")),
            total_tokens=_optional_int(total_tokens),
        )


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None

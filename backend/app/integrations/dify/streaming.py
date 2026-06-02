import json
import logging
from typing import Any

from app.integrations.dify.output import normalize_dify_final_output
from app.integrations.dify.schemas import DifyChatChunk

logger = logging.getLogger(__name__)


def parse_sse_lines(line: str) -> DifyChatChunk | None:
    if not line.startswith("data:"):
        return None
    raw = line.removeprefix("data:").strip()
    if not raw or raw == "[DONE]":
        return None

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        logger.debug("Dify non-JSON SSE line: %s", line[:100])
        return None

    event = payload.get("event", "message")
    metadata = payload.get("metadata") or {}

    # message_end 的 answer 是完整文本，不应作为增量 chunk 输出
    if event == "message_end":
        return DifyChatChunk(
            event=event,
            answer=None,
            conversation_id=payload.get("conversation_id"),
            message_id=payload.get("message_id"),
            metadata=metadata,
        )

    # Dify 不同 App 类型的回答位置不同：
    #   Chatbot:    event=message,     answer="..."
    #   Agent:      event=agent_message, answer="..."
    #   Workflow:   event=workflow_finished, data.outputs.text="..."
    #   Agent 思考: event=agent_thought, thought="...", answer="..."
    answer = payload.get("answer")
    error_message: str | None = None
    workflow_outputs_from_answer = None
    if isinstance(answer, str):
        normalized_answer = normalize_dify_final_output(answer)
        if normalized_answer.parsed and (
            normalized_answer.lead_deltas or normalized_answer.followup_decision.reason
        ):
            answer = normalized_answer.text
            workflow_outputs_from_answer = normalized_answer.to_public_dict()
    outputs = None
    if event == "workflow_finished":
        data = payload.get("data") or {}
        outputs = data.get("outputs") or {}
        if data.get("status") == "failed" or data.get("error"):
            answer = None
            error_message = data.get("error") or "Dify workflow failed"
        elif not answer:
            normalized = normalize_dify_final_output(outputs)
            answer = normalized.text or outputs.get("answer")
    # 提取 agent_thought 的思考过程
    thought = payload.get("thought")
    # 提取 workflow 节点事件（含重试状态，用于前端步骤展示）
    node: dict[str, Any] | None = None
    if event in ("workflow_started", "node_started", "node_finished", "workflow_finished", "node_retry"):
        data = payload.get("data")
        if isinstance(data, dict):
            node = {"event": event, **data}

    # Dify 顶层 error 事件：提取错误信息为结构化 chunk，避免在 runtime 层被过滤丢弃
    if event == "error":
        error_message = payload.get("message") or str(payload)
    return DifyChatChunk(
        event=event,
        answer=answer,
        thought=thought,
        conversation_id=payload.get("conversation_id"),
        message_id=payload.get("message_id"),
        metadata=metadata,
        node=node,
        workflow_outputs=(
            outputs if isinstance(outputs, dict)
            else workflow_outputs_from_answer
        ),
        error=error_message,
    )

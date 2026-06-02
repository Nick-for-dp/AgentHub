import json
from collections.abc import AsyncIterator
from time import perf_counter
from uuid import uuid4

import asyncio

from fastapi import APIRouter, Depends, Header
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.enums import (
    CallerType,
    ConversationMessageRole,
    ConversationMessageStatus,
    InvocationStatus,
    ResourceType,
)
from app.core.exceptions import DifyIntegrationError
from app.db.session import get_db
from app.integrations.dify.output import NormalizedDifyOutput, normalize_dify_final_output
from app.modules.agent.runtime import AgentRuntimeService
from app.modules.agent.service import AgentService
from app.modules.auth.dependencies import get_current_subject
from app.modules.auth.schemas import AuthenticatedSubject
from app.modules.auth.service import AuthService
from app.modules.conversation.models import Conversation, ConversationMessage
from app.modules.conversation.schemas import ConversationMessageCreate, ConversationMessageUpdate
from app.modules.conversation.service import ConversationService
from app.modules.invocation.schemas import InvocationRecordCreate, InvocationRecordFinish
from app.modules.invocation.service import InvocationService
from app.modules.lead.schemas import LeadCaptureContext
from app.modules.lead.service import LeadService

router = APIRouter()


class ChatRequest(BaseModel):
    question: str = Field(min_length=1)
    conversation_id: str | None = None
    stream: bool = True


@router.post("/{agent_code}")
async def chat(
    agent_code: str,
    payload: ChatRequest,
    x_request_id: str | None = Header(default=None),
    subject: AuthenticatedSubject = Depends(get_current_subject),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    request_id = x_request_id or str(uuid4())
    agent_service = AgentService(db)
    auth_service = AuthService(db)
    invocation_service = InvocationService(db)
    conversation_service = ConversationService(db)
    lead_service = LeadService(db)

    agent = agent_service.get_agent_by_code(agent_code)
    auth_service.assert_allowed(subject, ResourceType.AGENT, agent.id, "invoke")
    platform_conversation: Conversation | None = None
    assistant_message: ConversationMessage | None = None
    provider_conversation_id = payload.conversation_id
    is_user_chat = subject.caller_type == CallerType.USER and subject.user_id is not None

    if is_user_chat:
        platform_conversation = conversation_service.ensure_active_conversation(
            agent=agent,
            user_id=subject.user_id,
            org_unit_id=subject.org_unit_id,
            conversation_id=payload.conversation_id,
            first_question=payload.question,
        )
        provider_conversation_id = platform_conversation.provider_conversation_id
        conversation_service.create_message(
            ConversationMessageCreate(
                conversation_id=platform_conversation.id,
                role=ConversationMessageRole.USER,
                content=payload.question,
                status=ConversationMessageStatus.COMPLETED,
            )
        )

    known_lead_state = lead_service.load_known_lead_state(
        conversation=platform_conversation,
        agent=agent,
        user_id=subject.user_id,
    )

    record = invocation_service.create_record(
        InvocationRecordCreate(
            request_id=request_id,
            agent_id=agent.id,
            org_unit_id=subject.org_unit_id,
            user_id=subject.user_id,
            api_key_id=subject.api_key_id,
            caller_type=subject.caller_type,
            source_channel="WEB_CHAT" if subject.caller_type == "USER" else "EXTERNAL_API",
            input={"question": payload.question},
            stream_mode=payload.stream,
            session_id=platform_conversation.id if platform_conversation else payload.conversation_id,
        )
    )
    if platform_conversation is not None:
        assistant_message = conversation_service.create_message(
            ConversationMessageCreate(
                conversation_id=platform_conversation.id,
                role=ConversationMessageRole.ASSISTANT,
                status=ConversationMessageStatus.STREAMING,
            )
        )

    async def event_stream() -> AsyncIterator[str]:
        nonlocal provider_conversation_id
        started_at = perf_counter()
        output_parts: list[str] = []
        thought_parts: list[str] = []
        # 从 Dify message_end 事件中收集的 metadata，用于填充调用记录的审计字段
        last_metadata: dict = {}
        # workflow 节点事件轨迹，记录每个节点的开始/结束/状态/耗时
        node_trace: list[dict] = []
        provider_message_id: str | None = None
        final_workflow_outputs: dict | None = None
        normalized_output: NormalizedDifyOutput | None = None
        lead_capture_result: dict | None = None
        base_runtime_snapshot = {"runtime_type": agent.runtime_type, "runtime_app_id": agent.runtime_app_id}

        def _build_finish(**overrides) -> InvocationRecordFinish:
            """构造 InvocationRecordFinish，自动映射 Dify metadata 到审计字段。"""
            runtime_snapshot = dict(base_runtime_snapshot)
            if node_trace:
                runtime_snapshot["node_trace"] = node_trace
            if last_metadata:
                runtime_snapshot["dify_metadata"] = last_metadata
            if normalized_output is not None:
                runtime_snapshot["dify_final_output"] = normalized_output.to_public_dict()
            if lead_capture_result is not None:
                runtime_snapshot["lead_capture_result"] = lead_capture_result
            return InvocationRecordFinish(
                output=(
                    {"answer": normalized_output.text, **normalized_output.to_public_dict()}
                    if normalized_output is not None
                    else {"answer": "".join(output_parts)}
                ),
                token_usage=last_metadata.get("usage", {}),
                retrieval_snapshot={"resources": last_metadata.get("retriever_resources", [])},
                model_snapshot={"model_provider": last_metadata.get("model_provider"),
                                "model_name": last_metadata.get("model_name")}
                if any(k in last_metadata for k in ("model_provider", "model_name")) else {},
                runtime_snapshot=runtime_snapshot,
                **overrides,
            )

        try:
            if platform_conversation is not None:
                yield f"data: {json.dumps({'conversation_id': platform_conversation.id}, ensure_ascii=False)}\n\n"
            async for chunk in AgentRuntimeService().stream_chat(
                agent=agent,
                question=payload.question,
                caller_id=subject.user_id or subject.api_key_id or "anonymous",
                conversation_id=provider_conversation_id,
                extra_inputs={"known_lead_state": known_lead_state},
            ):
                if chunk.metadata:
                    last_metadata = chunk.metadata
                if chunk.workflow_outputs:
                    final_workflow_outputs = chunk.workflow_outputs
                # 累加工作流节点轨迹（用于审计快照）
                if chunk.node:
                    node_trace.append(chunk.node)
                event_data: dict = {}
                if chunk.answer:
                    output_parts.append(chunk.answer)
                    event_data["answer"] = chunk.answer
                if chunk.thought:
                    thought_parts.append(chunk.thought)
                    event_data["thought"] = chunk.thought
                if chunk.conversation_id and platform_conversation is None:
                    event_data["conversation_id"] = chunk.conversation_id
                if chunk.conversation_id and platform_conversation is not None:
                    provider_conversation_id = chunk.conversation_id
                    conversation_service.update_provider_conversation_id(
                        platform_conversation,
                        chunk.conversation_id,
                        commit=False,
                    )
                    event_data["provider_conversation_id"] = chunk.conversation_id
                if chunk.message_id:
                    provider_message_id = chunk.message_id
                    event_data["message_id"] = chunk.message_id
                if chunk.node:
                    event_data["event"] = chunk.node.get("event")
                    event_data["node"] = {k: v for k, v in chunk.node.items() if k != "event"}
                if chunk.error:
                    raise DifyIntegrationError(chunk.error)
                if assistant_message is not None and (
                    chunk.answer or chunk.thought or chunk.node or chunk.message_id
                ):
                    conversation_service.update_message(
                        assistant_message,
                        ConversationMessageUpdate(
                            content="".join(output_parts),
                            thought="".join(thought_parts) or None,
                            steps=node_trace,
                            provider_message_id=provider_message_id,
                            status=ConversationMessageStatus.STREAMING,
                        ),
                    )
                if event_data:
                    yield f"data: {json.dumps(event_data, ensure_ascii=False)}\n\n"
            normalized_output = normalize_dify_final_output(
                final_workflow_outputs if final_workflow_outputs is not None else {"text": "".join(output_parts)}
            )
            if output_parts and "".join(output_parts) != normalized_output.text:
                output_parts[:] = [normalized_output.text]
            if normalized_output.lead_deltas:
                lead_capture = lead_service.capture_output(
                    output=normalized_output,
                    context=LeadCaptureContext.from_chat(
                        agent=agent,
                        user_id=subject.user_id,
                        org_unit_id=subject.org_unit_id,
                        conversation=platform_conversation,
                        assistant_message=assistant_message,
                        invocation_record_id=record.id,
                    ),
                )
                lead_capture_result = lead_capture.model_dump()
            latency_ms = int((perf_counter() - started_at) * 1000)
            invocation_service.finish_record(
                record.id,
                _build_finish(status=InvocationStatus.SUCCEEDED, latency_ms=latency_ms),
            )
            if assistant_message is not None:
                conversation_service.update_message(
                    assistant_message,
                    ConversationMessageUpdate(
                        content="".join(output_parts),
                        thought="".join(thought_parts) or None,
                        steps=node_trace,
                        provider_message_id=provider_message_id,
                        invocation_record_id=record.id,
                        status=ConversationMessageStatus.COMPLETED,
                    ),
                )
            yield f"data: {json.dumps({'event': 'done'}, ensure_ascii=False)}\n\n"
        except asyncio.CancelledError:
            latency_ms = int((perf_counter() - started_at) * 1000)
            invocation_service.finish_record(
                record.id,
                _build_finish(
                    status=InvocationStatus.FAILED,
                    error_code="CLIENT_DISCONNECTED",
                    error_message="客户端主动断开连接",
                    latency_ms=latency_ms,
                ),
            )
            if assistant_message is not None:
                conversation_service.update_message(
                    assistant_message,
                    ConversationMessageUpdate(
                        content="".join(output_parts),
                        thought="".join(thought_parts) or None,
                        steps=node_trace,
                        provider_message_id=provider_message_id,
                        invocation_record_id=record.id,
                        status=ConversationMessageStatus.INTERRUPTED,
                    ),
                )
            raise
        except Exception as exc:
            latency_ms = int((perf_counter() - started_at) * 1000)
            invocation_service.finish_record(
                record.id,
                _build_finish(
                    status=InvocationStatus.FAILED,
                    error_code=exc.__class__.__name__,
                    error_message=str(exc),
                    latency_ms=latency_ms,
                ),
            )
            if assistant_message is not None:
                conversation_service.update_message(
                    assistant_message,
                    ConversationMessageUpdate(
                        content="".join(output_parts),
                        thought="".join(thought_parts) or None,
                        steps=node_trace,
                        provider_message_id=provider_message_id,
                        invocation_record_id=record.id,
                        status=ConversationMessageStatus.FAILED,
                    ),
                )
            yield f"data: {json.dumps({'event': 'error', 'message': str(exc)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")

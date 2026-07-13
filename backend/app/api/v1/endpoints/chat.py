import asyncio
import json
from collections.abc import AsyncIterator
from time import perf_counter
from uuid import uuid4

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
from app.core.exceptions import ForbiddenError
from app.db.session import get_db
from app.modules.agent.handlers import ChatContext, get_chat_handler_registry
from app.modules.agent.runtime import AgentRuntimeService
from app.modules.agent.service import AgentService
from app.modules.auth.dependencies import get_current_subject
from app.modules.auth.schemas import AuthenticatedSubject
from app.modules.auth.service import AuthService
from app.modules.conversation.schemas import ConversationMessageCreate, ConversationMessageUpdate
from app.modules.conversation.service import ConversationService
from app.modules.invocation.schemas import InvocationRecordCreate
from app.modules.invocation.service import InvocationService
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
    """对话流入口（ChatHandler 路径）。

    endpoint 只做四件事：鉴权 → 取 Agent → 选 ChatHandler → 写调用记录与产品会话。
    流式消费、Dify 归一化、线索收集等逻辑由 ChatHandler 承载，endpoint 不感知
    runtime provider 专有类型。

    任务型 Agent（如合同审查）不走本路径，由 internal 任务 API + TaskHandler 流水线执行。
    """
    request_id = x_request_id or str(uuid4())
    agent_service = AgentService(db)
    auth_service = AuthService(db)
    invocation_service = InvocationService(db)
    conversation_service = ConversationService(db)
    lead_service = LeadService(db)

    agent = agent_service.get_agent_by_code(agent_code)
    if subject.embed_session_id is not None:
        if subject.embed_agent_code != agent_code:
            raise ForbiddenError("embed session cannot access this agent")
    else:
        auth_service.assert_allowed(subject, ResourceType.AGENT, agent.id, "invoke")

    # 选 ChatHandler：按 agent.type 分发对话流处理器，未注册类型返回明确错误
    handler = get_chat_handler_registry().select(agent)
    handler.set_base_runtime_snapshot(agent)

    platform_conversation = None
    assistant_message = None
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

    ctx = ChatContext(
        agent=agent,
        subject=subject,
        question=payload.question,
        provider_conversation_id=provider_conversation_id,
        platform_conversation=platform_conversation,
        assistant_message=assistant_message,
        known_lead_state=known_lead_state,
        runtime_service=AgentRuntimeService(),
        conversation_service=conversation_service,
        invocation_record_id=record.id,
    )

    async def event_stream() -> AsyncIterator[str]:
        started_at = perf_counter()

        def _latency_ms() -> int:
            return int((perf_counter() - started_at) * 1000)

        def _finish_message(status: ConversationMessageStatus) -> None:
            """更新 assistant 消息最终状态（仅登录用户有产品会话时）。"""
            if assistant_message is not None:
                finish = handler.build_finish(status=InvocationStatus.SUCCEEDED.name)
                conversation_service.update_message(
                    assistant_message,
                    ConversationMessageUpdate(
                        content=finish.output.get("answer", ""),
                        thought=None,
                        steps=[],
                        provider_message_id=handler._provider_message_id,
                        invocation_record_id=record.id,
                        status=status,
                    ),
                )

        try:
            if platform_conversation is not None:
                yield f"data: {json.dumps({'conversation_id': platform_conversation.id}, ensure_ascii=False)}\n\n"
            async for event_data in handler.stream(ctx):
                yield f"data: {json.dumps(event_data, ensure_ascii=False)}\n\n"

            # 流正常结束：归一化输出 + 运行后处理器
            handler.on_complete(ctx, lead_service)

            finish = handler.build_finish(
                status=InvocationStatus.SUCCEEDED,
                latency_ms=_latency_ms(),
            )
            invocation_service.finish_record(record.id, finish)
            if assistant_message is not None:
                conversation_service.update_message(
                    assistant_message,
                    ConversationMessageUpdate(
                        content=finish.output.get("answer", ""),
                        thought="".join(handler._thought_parts) or None,
                        steps=handler._node_trace,
                        provider_message_id=handler._provider_message_id,
                        invocation_record_id=record.id,
                        status=ConversationMessageStatus.COMPLETED,
                    ),
                )
            yield f"data: {json.dumps({'event': 'done'}, ensure_ascii=False)}\n\n"

        except asyncio.CancelledError:
            finish = handler.build_finish(
                status=InvocationStatus.FAILED,
                error_code="CLIENT_DISCONNECTED",
                error_message="客户端主动断开连接",
                latency_ms=_latency_ms(),
            )
            invocation_service.finish_record(record.id, finish)
            if assistant_message is not None:
                conversation_service.update_message(
                    assistant_message,
                    ConversationMessageUpdate(
                        content="".join(handler._output_parts),
                        thought="".join(handler._thought_parts) or None,
                        steps=handler._node_trace,
                        provider_message_id=handler._provider_message_id,
                        invocation_record_id=record.id,
                        status=ConversationMessageStatus.INTERRUPTED,
                    ),
                )
            raise

        except Exception as exc:
            finish = handler.build_finish(
                status=InvocationStatus.FAILED,
                error_code=exc.__class__.__name__,
                error_message=str(exc),
                latency_ms=_latency_ms(),
            )
            invocation_service.finish_record(record.id, finish)
            if assistant_message is not None:
                conversation_service.update_message(
                    assistant_message,
                    ConversationMessageUpdate(
                        content="".join(handler._output_parts),
                        thought="".join(handler._thought_parts) or None,
                        steps=handler._node_trace,
                        provider_message_id=handler._provider_message_id,
                        invocation_record_id=record.id,
                        status=ConversationMessageStatus.FAILED,
                    ),
                )
            yield f"data: {json.dumps({'event': 'error', 'message': str(exc)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
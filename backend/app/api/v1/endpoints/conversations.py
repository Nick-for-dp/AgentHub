from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.enums import CallerType, ConversationStatus, ResourceType
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.responses import APIResponse, success
from app.db.session import get_db
from app.modules.agent.service import AgentService
from app.modules.auth.dependencies import get_current_subject
from app.modules.auth.schemas import AuthenticatedSubject
from app.modules.auth.service import AuthService
from app.modules.conversation.schemas import (
    ConversationMessageRead,
    ConversationPage,
    ConversationRead,
    ConversationUpdate,
    ConversationWithMessages,
)
from app.modules.conversation.service import ConversationService

router = APIRouter()


class ConversationStartRequest(BaseModel):
    agent_code: str = Field(default="qa", min_length=1)
    title: str | None = Field(default=None, max_length=200)


def _require_session_user(subject: AuthenticatedSubject) -> str:
    if subject.caller_type != CallerType.USER or subject.user_id is None:
        raise UnauthorizedError("conversation requires user session")
    return subject.user_id


def _assert_agent_access(
    *,
    db: Session,
    subject: AuthenticatedSubject,
    agent_code: str,
):
    agent = AgentService(db).get_agent_by_code(agent_code)
    if subject.embed_session_id is not None:
        if subject.embed_agent_code != agent_code:
            raise ForbiddenError("embed session cannot access this agent")
    else:
        AuthService(db).assert_allowed(subject, ResourceType.AGENT, agent.id, "invoke")
    return agent


@router.get("/current", response_model=APIResponse[ConversationWithMessages])
def get_current_conversation(
    agent_code: str = Query(default="qa", min_length=1),
    subject: AuthenticatedSubject = Depends(get_current_subject),
    db: Session = Depends(get_db),
) -> APIResponse[ConversationWithMessages]:
    user_id = _require_session_user(subject)
    agent = _assert_agent_access(db=db, subject=subject, agent_code=agent_code)
    service = ConversationService(db)
    conversation = service.get_current_conversation(user_id=user_id, agent=agent)
    if conversation is None:
        return success(ConversationWithMessages())
    messages = service.list_messages_for_user(conversation_id=conversation.id, user_id=user_id)
    return success(
        ConversationWithMessages(
            conversation=ConversationRead.model_validate(conversation),
            messages=[ConversationMessageRead.model_validate(item) for item in messages],
        )
    )


@router.post("", response_model=APIResponse[ConversationRead])
def create_conversation(
    payload: ConversationStartRequest,
    subject: AuthenticatedSubject = Depends(get_current_subject),
    db: Session = Depends(get_db),
) -> APIResponse[ConversationRead]:
    user_id = _require_session_user(subject)
    agent = _assert_agent_access(db=db, subject=subject, agent_code=payload.agent_code)
    conversation = ConversationService(db).create_for_agent(
        agent=agent,
        user_id=user_id,
        org_unit_id=subject.org_unit_id,
        title=payload.title,
    )
    return success(ConversationRead.model_validate(conversation))


@router.get("", response_model=APIResponse[ConversationPage])
def list_conversations(
    agent_code: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    subject: AuthenticatedSubject = Depends(get_current_subject),
    db: Session = Depends(get_db),
) -> APIResponse[ConversationPage]:
    user_id = _require_session_user(subject)
    if agent_code:
        _assert_agent_access(db=db, subject=subject, agent_code=agent_code)
    items, total = ConversationService(db).list_conversations(
        user_id=user_id,
        agent_code=agent_code,
        page=page,
        page_size=page_size,
    )
    return success(
        ConversationPage(
            items=[ConversationRead.model_validate(item) for item in items],
            total=total,
            page=page,
            page_size=page_size,
        )
    )


@router.get("/{conversation_id}", response_model=APIResponse[ConversationRead])
def get_conversation(
    conversation_id: str,
    subject: AuthenticatedSubject = Depends(get_current_subject),
    db: Session = Depends(get_db),
) -> APIResponse[ConversationRead]:
    user_id = _require_session_user(subject)
    conversation = ConversationService(db).get_user_conversation(
        conversation_id=conversation_id,
        user_id=user_id,
    )
    return success(ConversationRead.model_validate(conversation))


@router.get("/{conversation_id}/messages", response_model=APIResponse[list[ConversationMessageRead]])
def list_conversation_messages(
    conversation_id: str,
    subject: AuthenticatedSubject = Depends(get_current_subject),
    db: Session = Depends(get_db),
) -> APIResponse[list[ConversationMessageRead]]:
    user_id = _require_session_user(subject)
    messages = ConversationService(db).list_messages_for_user(
        conversation_id=conversation_id,
        user_id=user_id,
    )
    return success([ConversationMessageRead.model_validate(item) for item in messages])


@router.patch("/{conversation_id}", response_model=APIResponse[ConversationRead])
def update_conversation(
    conversation_id: str,
    payload: ConversationUpdate,
    subject: AuthenticatedSubject = Depends(get_current_subject),
    db: Session = Depends(get_db),
) -> APIResponse[ConversationRead]:
    user_id = _require_session_user(subject)
    conversation = ConversationService(db).update_conversation(
        conversation_id=conversation_id,
        user_id=user_id,
        payload=payload,
    )
    return success(ConversationRead.model_validate(conversation))


@router.delete("/{conversation_id}", response_model=APIResponse[None])
def delete_conversation(
    conversation_id: str,
    subject: AuthenticatedSubject = Depends(get_current_subject),
    db: Session = Depends(get_db),
) -> APIResponse[None]:
    user_id = _require_session_user(subject)
    ConversationService(db).soft_delete_conversation(conversation_id=conversation_id, user_id=user_id)
    return success(None)

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.enums import (
    ConversationMessageRole,
    ConversationMessageStatus,
    ConversationStatus,
    ProviderType,
)
from app.core.exceptions import ForbiddenError, NotFoundError
from app.modules.agent.models import Agent
from app.modules.agent.repository import AgentRepository
from app.modules.conversation.models import Conversation, ConversationMessage
from app.modules.conversation.repository import ConversationRepository
from app.modules.conversation.schemas import (
    ConversationCreate,
    ConversationMessageCreate,
    ConversationMessageUpdate,
    ConversationUpdate,
)


class ConversationService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = ConversationRepository(db)
        self.agent_repository = AgentRepository(db)

    def create_conversation(self, payload: ConversationCreate) -> Conversation:
        conversation = Conversation(**payload.model_dump())
        self.repository.add_conversation(conversation)
        self.db.commit()
        self.db.refresh(conversation)
        return conversation

    def create_for_agent(
        self,
        *,
        agent: Agent,
        user_id: str,
        org_unit_id: str | None,
        title: str | None = None,
    ) -> Conversation:
        return self.create_conversation(
            ConversationCreate(
                agent_id=agent.id,
                agent_code=agent.code,
                user_id=user_id,
                org_unit_id=org_unit_id,
                title=self.build_title(title),
                provider=ProviderType.DIFY,
            )
        )

    def get_current_conversation(
        self,
        *,
        user_id: str,
        agent: Agent,
    ) -> Conversation | None:
        conversation = self.repository.get_latest_active_conversation(
            user_id=user_id,
            agent_id=agent.id,
        )
        if conversation is None:
            return None
        if self.is_inactive(conversation):
            conversation.status = ConversationStatus.ARCHIVED
            self.repository.save_conversation(conversation)
            self.db.commit()
            return None
        return conversation

    def get_user_conversation(
        self,
        *,
        conversation_id: str,
        user_id: str,
        agent_id: str | None = None,
        include_deleted: bool = False,
    ) -> Conversation:
        conversation = self.repository.get_conversation(conversation_id)
        if conversation is None:
            raise NotFoundError("conversation not found")
        if conversation.user_id != user_id:
            raise NotFoundError("conversation not found")
        if agent_id and conversation.agent_id != agent_id:
            raise ForbiddenError("conversation does not belong to this agent")
        if not include_deleted and conversation.status == ConversationStatus.DELETED:
            raise NotFoundError("conversation not found")
        return conversation

    def list_conversations(
        self,
        *,
        user_id: str,
        agent_code: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Conversation], int]:
        agent_id = None
        if agent_code:
            agent = self.agent_repository.get_agent_by_code(agent_code)
            if agent is None:
                return [], 0
            agent_id = agent.id
        return self.repository.list_conversations(
            user_id=user_id,
            agent_id=agent_id,
            page=page,
            page_size=page_size,
        )

    def update_conversation(
        self,
        *,
        conversation_id: str,
        user_id: str,
        payload: ConversationUpdate,
    ) -> Conversation:
        conversation = self.get_user_conversation(
            conversation_id=conversation_id,
            user_id=user_id,
            include_deleted=True,
        )
        update_data = payload.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(conversation, field, value)
        self.repository.save_conversation(conversation)
        self.db.commit()
        self.db.refresh(conversation)
        return conversation

    def soft_delete_conversation(self, *, conversation_id: str, user_id: str) -> None:
        conversation = self.get_user_conversation(conversation_id=conversation_id, user_id=user_id)
        conversation.status = ConversationStatus.DELETED
        self.repository.save_conversation(conversation)
        self.db.commit()

    def archive_conversation(self, conversation: Conversation) -> Conversation:
        conversation.status = ConversationStatus.ARCHIVED
        self.repository.save_conversation(conversation)
        self.db.commit()
        self.db.refresh(conversation)
        return conversation

    def ensure_active_conversation(
        self,
        *,
        agent: Agent,
        user_id: str,
        org_unit_id: str | None,
        conversation_id: str | None,
        first_question: str,
    ) -> Conversation:
        if conversation_id:
            conversation = self.get_user_conversation(
                conversation_id=conversation_id,
                user_id=user_id,
                agent_id=agent.id,
            )
            if self.is_inactive(conversation):
                return self.create_for_agent(
                    agent=agent,
                    user_id=user_id,
                    org_unit_id=org_unit_id,
                    title=first_question,
                )
            return conversation

        conversation = self.get_current_conversation(user_id=user_id, agent=agent)
        if conversation is not None:
            return conversation
        return self.create_for_agent(
            agent=agent,
            user_id=user_id,
            org_unit_id=org_unit_id,
            title=first_question,
        )

    def create_message(self, payload: ConversationMessageCreate) -> ConversationMessage:
        message = ConversationMessage(
            **payload.model_dump(),
            sequence_no=self.repository.next_message_sequence(payload.conversation_id),
        )
        self.repository.add_message(message)
        conversation = self.repository.get_conversation(payload.conversation_id)
        if conversation is not None:
            self.repository.touch_last_message_at(conversation, message.created_at)
        self.db.commit()
        self.db.refresh(message)
        return message

    def update_message(
        self,
        message: ConversationMessage,
        payload: ConversationMessageUpdate,
        *,
        commit: bool = True,
    ) -> ConversationMessage:
        update_data = payload.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(message, field, value)
        self.repository.save_message(message)
        conversation = self.repository.get_conversation(message.conversation_id)
        if conversation is not None:
            self.repository.touch_last_message_at(conversation, datetime.now(timezone.utc))
        if commit:
            self.db.commit()
            self.db.refresh(message)
        return message

    def update_provider_conversation_id(
        self,
        conversation: Conversation,
        provider_conversation_id: str,
        *,
        commit: bool = True,
    ) -> Conversation:
        if conversation.provider_conversation_id == provider_conversation_id:
            return conversation
        conversation.provider_conversation_id = provider_conversation_id
        self.repository.save_conversation(conversation)
        if commit:
            self.db.commit()
            self.db.refresh(conversation)
        return conversation

    def list_messages_for_user(self, *, conversation_id: str, user_id: str) -> list[ConversationMessage]:
        conversation = self.get_user_conversation(conversation_id=conversation_id, user_id=user_id)
        return self.repository.list_messages(conversation.id)

    def is_inactive(self, conversation: Conversation) -> bool:
        threshold = datetime.now(timezone.utc) - timedelta(hours=get_settings().conversation_inactive_hours)
        return self._as_utc(conversation.last_message_at) <= threshold

    @staticmethod
    def build_title(text: str | None) -> str:
        value = (text or "").strip()
        if not value:
            return "新对话"
        return value[:30]

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

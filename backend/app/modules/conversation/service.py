from datetime import datetime, timezone

from sqlalchemy.orm import Session
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
    DEFAULT_TITLE = "新对话"

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
        """返回用户当前 Agent 下最新的 ACTIVE 会话，不再因 24h 不活跃自动归档。"""
        conversation = self.repository.get_latest_active_conversation(
            user_id=user_id,
            agent_id=agent.id,
        )
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
        """确保存在可用会话。传入 conversation_id 时直接恢复；否则取最新 ACTIVE，没有则新建。

        传入的 conversation_id 在库中不存在时（如客户端 URL 残留了已删除或重建库前的旧 ID），
        不抛 404 阻断聊天，而是静默回退到“取当前 ACTIVE / 新建”。
        但归属校验仍然生效：会话属于其他用户或其他 Agent 时必须拒绝，不能借回退绕过越权。
        """
        if conversation_id:
            existing = self.repository.get_conversation(conversation_id)
            # 不存在或已删除：视为无效 ID，丢弃后走下方“当前/新建”回退逻辑
            if existing is not None and existing.status != ConversationStatus.DELETED:
                if existing.user_id != user_id:
                    raise NotFoundError("conversation not found")
                if existing.agent_id != agent.id:
                    raise ForbiddenError("conversation does not belong to this agent")
                if existing.status == ConversationStatus.ARCHIVED:
                    existing.status = ConversationStatus.ACTIVE
                    self.repository.save_conversation(existing)
                    self.db.commit()
                    self.db.refresh(existing)
                return existing

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
            if (
                payload.role == ConversationMessageRole.USER
                and message.sequence_no == 1
                and self._is_default_title(conversation.title)
                and payload.content.strip()
            ):
                conversation.title = self.build_title(payload.content)
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

    @staticmethod
    def build_title(text: str | None) -> str:
        value = (text or "").strip()
        if not value:
            return ConversationService.DEFAULT_TITLE
        return value[:30]

    @classmethod
    def _is_default_title(cls, title: str | None) -> bool:
        return not (title or "").strip() or title == cls.DEFAULT_TITLE

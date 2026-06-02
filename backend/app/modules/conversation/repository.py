from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.enums import ConversationStatus
from app.modules.conversation.models import Conversation, ConversationMessage


class ConversationRepository:
    def __init__(self, db: Session):
        self.db = db

    def add_conversation(self, conversation: Conversation) -> Conversation:
        self.db.add(conversation)
        self.db.flush()
        return conversation

    def save_conversation(self, conversation: Conversation) -> Conversation:
        self.db.add(conversation)
        self.db.flush()
        return conversation

    def get_conversation(self, conversation_id: str) -> Conversation | None:
        return self.db.get(Conversation, conversation_id)

    def get_latest_active_conversation(
        self,
        *,
        user_id: str,
        agent_id: str,
    ) -> Conversation | None:
        stmt = (
            select(Conversation)
            .where(
                Conversation.user_id == user_id,
                Conversation.agent_id == agent_id,
                Conversation.status == ConversationStatus.ACTIVE,
            )
            .order_by(Conversation.last_message_at.desc())
            .limit(1)
        )
        return self.db.scalars(stmt).first()

    def list_conversations(
        self,
        *,
        user_id: str,
        agent_id: str | None = None,
        include_deleted: bool = False,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Conversation], int]:
        stmt = select(Conversation).where(Conversation.user_id == user_id)
        if agent_id:
            stmt = stmt.where(Conversation.agent_id == agent_id)
        if not include_deleted:
            stmt = stmt.where(Conversation.status != ConversationStatus.DELETED)

        total = self.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        offset = (page - 1) * page_size
        stmt = stmt.order_by(Conversation.last_message_at.desc()).limit(page_size).offset(offset)
        return list(self.db.scalars(stmt)), total

    def next_message_sequence(self, conversation_id: str) -> int:
        stmt = select(func.max(ConversationMessage.sequence_no)).where(
            ConversationMessage.conversation_id == conversation_id
        )
        current = self.db.scalar(stmt) or 0
        return int(current) + 1

    def add_message(self, message: ConversationMessage) -> ConversationMessage:
        self.db.add(message)
        self.db.flush()
        return message

    def save_message(self, message: ConversationMessage) -> ConversationMessage:
        self.db.add(message)
        self.db.flush()
        return message

    def list_messages(self, conversation_id: str) -> list[ConversationMessage]:
        stmt = (
            select(ConversationMessage)
            .where(ConversationMessage.conversation_id == conversation_id)
            .order_by(ConversationMessage.sequence_no.asc(), ConversationMessage.created_at.asc())
        )
        return list(self.db.scalars(stmt))

    def touch_last_message_at(self, conversation: Conversation, value: datetime) -> Conversation:
        conversation.last_message_at = value
        self.db.add(conversation)
        self.db.flush()
        return conversation

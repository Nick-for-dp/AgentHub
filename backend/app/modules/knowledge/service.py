from sqlalchemy.orm import Session

from app.core.enums import ParseStatus, ResourceStatus
from app.core.exceptions import NotFoundError
from app.modules.knowledge.models import Document, KnowledgeBase
from app.modules.knowledge.repository import KnowledgeRepository
from app.modules.knowledge.schemas import DocumentCreate, KnowledgeBaseCreate


class KnowledgeService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = KnowledgeRepository(db)

    def create_knowledge_base(self, payload: KnowledgeBaseCreate) -> KnowledgeBase:
        knowledge_base = KnowledgeBase(
            **payload.model_dump(),
            status=ResourceStatus.ACTIVE,
        )
        self.repository.add_knowledge_base(knowledge_base)
        self.db.commit()
        self.db.refresh(knowledge_base)
        return knowledge_base

    def create_document(self, payload: DocumentCreate) -> Document:
        if self.repository.get_knowledge_base(payload.knowledge_base_id) is None:
            raise NotFoundError("knowledge base not found")
        document = Document(
            **payload.model_dump(),
            parse_status=ParseStatus.PENDING,
        )
        self.repository.add_document(document)
        self.db.commit()
        self.db.refresh(document)
        return document

    def list_knowledge_bases(self) -> list[KnowledgeBase]:
        return self.repository.list_knowledge_bases()

    def list_documents(self) -> list[Document]:
        return self.repository.list_documents()

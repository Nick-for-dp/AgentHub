from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.knowledge.models import Document, KnowledgeBase


class KnowledgeRepository:
    def __init__(self, db: Session):
        self.db = db

    def add_knowledge_base(self, knowledge_base: KnowledgeBase) -> KnowledgeBase:
        self.db.add(knowledge_base)
        self.db.flush()
        return knowledge_base

    def get_knowledge_base(self, knowledge_base_id: str) -> KnowledgeBase | None:
        return self.db.get(KnowledgeBase, knowledge_base_id)

    def list_knowledge_bases(self, limit: int = 100, offset: int = 0) -> list[KnowledgeBase]:
        stmt = select(KnowledgeBase).order_by(KnowledgeBase.created_at.desc()).limit(limit).offset(offset)
        return list(self.db.scalars(stmt))

    def add_document(self, document: Document) -> Document:
        self.db.add(document)
        self.db.flush()
        return document

    def get_document(self, document_id: str) -> Document | None:
        return self.db.get(Document, document_id)

    def list_documents(self, limit: int = 100, offset: int = 0) -> list[Document]:
        stmt = select(Document).order_by(Document.created_at.desc()).limit(limit).offset(offset)
        return list(self.db.scalars(stmt))

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.responses import APIResponse, success
from app.db.session import get_db
from app.modules.knowledge.schemas import DocumentCreate, DocumentRead, KnowledgeBaseCreate, KnowledgeBaseRead
from app.modules.knowledge.service import KnowledgeService

router = APIRouter()


@router.get("", response_model=APIResponse[list[KnowledgeBaseRead]])
def list_knowledge_bases(db: Session = Depends(get_db)) -> APIResponse[list[KnowledgeBaseRead]]:
    items = [
        KnowledgeBaseRead.model_validate(item)
        for item in KnowledgeService(db).list_knowledge_bases()
    ]
    return success(items)


@router.post("", response_model=APIResponse[KnowledgeBaseRead])
def create_knowledge_base(
    payload: KnowledgeBaseCreate,
    db: Session = Depends(get_db),
) -> APIResponse[KnowledgeBaseRead]:
    knowledge_base = KnowledgeService(db).create_knowledge_base(payload)
    return success(KnowledgeBaseRead.model_validate(knowledge_base))


@router.post("/{knowledge_base_id}/documents", response_model=APIResponse[DocumentRead])
def create_document_under_knowledge_base(
    knowledge_base_id: str,
    payload: DocumentCreate,
    db: Session = Depends(get_db),
) -> APIResponse[DocumentRead]:
    payload.knowledge_base_id = knowledge_base_id
    document = KnowledgeService(db).create_document(payload)
    return success(DocumentRead.model_validate(document))

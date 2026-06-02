from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.responses import APIResponse, success
from app.db.session import get_db
from app.modules.knowledge.schemas import DocumentCreate, DocumentRead
from app.modules.knowledge.service import KnowledgeService

router = APIRouter()


@router.get("", response_model=APIResponse[list[DocumentRead]])
def list_documents(db: Session = Depends(get_db)) -> APIResponse[list[DocumentRead]]:
    items = [DocumentRead.model_validate(item) for item in KnowledgeService(db).list_documents()]
    return success(items)


@router.post("", response_model=APIResponse[DocumentRead])
def create_document(
    payload: DocumentCreate,
    db: Session = Depends(get_db),
) -> APIResponse[DocumentRead]:
    document = KnowledgeService(db).create_document(payload)
    return success(DocumentRead.model_validate(document))

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.responses import APIResponse, success
from app.db.session import get_db
from app.modules.auth.schemas import APIKeyCreateByPhone, APIKeyIssued, APIKeyRead
from app.modules.auth.service import AuthService

router = APIRouter()


@router.get("", response_model=APIResponse[list[APIKeyRead]])
def list_api_keys(db: Session = Depends(get_db)) -> APIResponse[list[APIKeyRead]]:
    items = [APIKeyRead.model_validate(item) for item in AuthService(db).list_api_keys()]
    return success(items)


@router.post("/by-phone", response_model=APIResponse[APIKeyIssued])
def issue_api_key_by_phone(
    payload: APIKeyCreateByPhone,
    db: Session = Depends(get_db),
) -> APIResponse[APIKeyIssued]:
    raw_key, record = AuthService(db).issue_external_customer_api_key_by_phone(payload)
    return success(APIKeyIssued(api_key=raw_key, record=APIKeyRead.model_validate(record)))

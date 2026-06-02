from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.responses import APIResponse, success
from app.db.session import get_db
from app.modules.org.schemas import UserCreate, UserRead
from app.modules.org.service import OrgService

router = APIRouter()


@router.get("", response_model=APIResponse[list[UserRead]])
def list_users(db: Session = Depends(get_db)) -> APIResponse[list[UserRead]]:
    items = [UserRead.model_validate(item) for item in OrgService(db).list_users()]
    return success(items)


@router.post("", response_model=APIResponse[UserRead])
def create_user(payload: UserCreate, db: Session = Depends(get_db)) -> APIResponse[UserRead]:
    user = OrgService(db).create_user(payload)
    return success(UserRead.model_validate(user))

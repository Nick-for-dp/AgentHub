from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.responses import APIResponse, success
from app.db.session import get_db
from app.modules.auth.schemas import PermissionPolicyCreate, PermissionPolicyRead
from app.modules.auth.service import AuthService

router = APIRouter()


@router.get("", response_model=APIResponse[list[PermissionPolicyRead]])
def list_permission_policies(
    db: Session = Depends(get_db),
) -> APIResponse[list[PermissionPolicyRead]]:
    items = [
        PermissionPolicyRead.model_validate(item)
        for item in AuthService(db).list_permission_policies()
    ]
    return success(items)


@router.post("", response_model=APIResponse[PermissionPolicyRead])
def create_permission_policy(
    payload: PermissionPolicyCreate,
    db: Session = Depends(get_db),
) -> APIResponse[PermissionPolicyRead]:
    policy = AuthService(db).create_permission_policy(payload)
    return success(PermissionPolicyRead.model_validate(policy))

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.responses import APIResponse, success
from app.db.session import get_db
from app.modules.org.schemas import OrgUnitCreate, OrgUnitRead
from app.modules.org.service import OrgService

router = APIRouter()


@router.get("", response_model=APIResponse[list[OrgUnitRead]])
def list_org_units(db: Session = Depends(get_db)) -> APIResponse[list[OrgUnitRead]]:
    items = [OrgUnitRead.model_validate(item) for item in OrgService(db).list_org_units()]
    return success(items)


@router.post("", response_model=APIResponse[OrgUnitRead])
def create_org_unit(
    payload: OrgUnitCreate,
    db: Session = Depends(get_db),
) -> APIResponse[OrgUnitRead]:
    org_unit = OrgService(db).create_org_unit(payload)
    return success(OrgUnitRead.model_validate(org_unit))

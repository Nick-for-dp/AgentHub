from sqlalchemy.orm import Session

from app.core.enums import ResourceStatus, UserType
from app.core.exceptions import ConflictError, NotFoundError
from app.core.security import hash_password, normalize_phone
from app.modules.org.models import OrgUnit, UserAccount
from app.modules.org.repository import OrgRepository
from app.modules.org.schemas import OrgUnitCreate, UserCreate


class OrgService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = OrgRepository(db)

    def create_org_unit(self, payload: OrgUnitCreate) -> OrgUnit:
        org_unit = OrgUnit(
            name=payload.name,
            type=payload.type,
            parent_id=payload.parent_id,
            status=ResourceStatus.ACTIVE,
        )
        self.repository.add_org_unit(org_unit)
        self.db.commit()
        self.db.refresh(org_unit)
        return org_unit

    def create_user(self, payload: UserCreate) -> UserAccount:
        if self.repository.get_org_unit(payload.org_unit_id) is None:
            raise NotFoundError("org unit not found")

        phone_normalized = normalize_phone(payload.phone) if payload.phone else None
        if payload.user_type == UserType.EXTERNAL_CUSTOMER and not phone_normalized:
            raise ConflictError("external customer phone is required")
        if phone_normalized and payload.user_type == UserType.EXTERNAL_CUSTOMER:
            if self.repository.phone_exists_for_external_user(phone_normalized):
                raise ConflictError("external customer phone already exists")

        user = UserAccount(
            org_unit_id=payload.org_unit_id,
            name=payload.name,
            user_type=payload.user_type,
            email=payload.email,
            phone=payload.phone,
            phone_normalized=phone_normalized,
            status=ResourceStatus.ACTIVE,
            remark=payload.remark,
            password_hash=hash_password(payload.password) if payload.password else None,
        )
        self.repository.add_user(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def list_org_units(self) -> list[OrgUnit]:
        return self.repository.list_org_units()

    def list_users(self) -> list[UserAccount]:
        return self.repository.list_users()

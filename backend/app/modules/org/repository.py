from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import OrgUnitType, ResourceStatus, UserType
from app.modules.org.models import OrgUnit, UserAccount


class OrgRepository:
    def __init__(self, db: Session):
        self.db = db

    def add_org_unit(self, org_unit: OrgUnit) -> OrgUnit:
        self.db.add(org_unit)
        self.db.flush()
        return org_unit

    def get_org_unit(self, org_unit_id: str) -> OrgUnit | None:
        return self.db.get(OrgUnit, org_unit_id)

    def get_org_unit_by_name_type(
        self,
        *,
        name: str,
        org_type: str = OrgUnitType.EXTERNAL_CUSTOMER,
    ) -> OrgUnit | None:
        stmt = select(OrgUnit).where(
            OrgUnit.name == name,
            OrgUnit.type == org_type,
            OrgUnit.status == ResourceStatus.ACTIVE,
        )
        return self.db.scalars(stmt).first()

    def list_org_units(self, limit: int = 100, offset: int = 0) -> list[OrgUnit]:
        stmt = select(OrgUnit).order_by(OrgUnit.created_at.desc()).limit(limit).offset(offset)
        return list(self.db.scalars(stmt))

    def add_user(self, user: UserAccount) -> UserAccount:
        self.db.add(user)
        self.db.flush()
        return user

    def get_user(self, user_id: str) -> UserAccount | None:
        return self.db.get(UserAccount, user_id)

    def get_active_external_user_by_phone(self, phone_normalized: str) -> UserAccount | None:
        stmt = select(UserAccount).where(
            UserAccount.user_type == UserType.EXTERNAL_CUSTOMER,
            UserAccount.status == ResourceStatus.ACTIVE,
            UserAccount.phone_normalized == phone_normalized,
        )
        return self.db.scalars(stmt).one_or_none()

    def phone_exists_for_external_user(self, phone_normalized: str) -> bool:
        stmt = select(UserAccount.id).where(
            UserAccount.user_type == UserType.EXTERNAL_CUSTOMER,
            UserAccount.phone_normalized == phone_normalized,
        )
        return self.db.scalars(stmt).first() is not None

    def list_users(self, limit: int = 100, offset: int = 0) -> list[UserAccount]:
        stmt = select(UserAccount).order_by(UserAccount.created_at.desc()).limit(limit).offset(offset)
        return list(self.db.scalars(stmt))

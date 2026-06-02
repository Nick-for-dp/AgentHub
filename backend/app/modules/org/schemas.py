from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.enums import OrgUnitType, ResourceStatus, UserType


class OrgUnitCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    type: OrgUnitType = OrgUnitType.EXTERNAL_CUSTOMER
    parent_id: str | None = None


class OrgUnitRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    type: OrgUnitType
    parent_id: str | None
    status: ResourceStatus
    created_at: datetime
    updated_at: datetime


class UserCreate(BaseModel):
    org_unit_id: str
    name: str = Field(min_length=1, max_length=100)
    user_type: UserType = UserType.EXTERNAL_CUSTOMER
    email: str | None = None
    phone: str | None = None
    password: str | None = Field(default=None, min_length=6, max_length=128)
    remark: str | None = None

    @field_validator("phone")
    @classmethod
    def strip_phone(cls, value: str | None) -> str | None:
        return value.strip() if value else value


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    org_unit_id: str
    name: str
    user_type: UserType
    email: str | None
    phone: str | None
    phone_normalized: str | None
    status: ResourceStatus
    remark: str | None
    created_at: datetime
    updated_at: datetime

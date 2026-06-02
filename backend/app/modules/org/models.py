from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import OrgUnitType, ResourceStatus, UserType
from app.db.base import Base
from app.db.mixins import IDMixin, TimestampMixin


class OrgUnit(IDMixin, TimestampMixin, Base):
    __tablename__ = "org_unit"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False, default=OrgUnitType.EXTERNAL_CUSTOMER)
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("org_unit.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=ResourceStatus.ACTIVE)

    parent: Mapped["OrgUnit | None"] = relationship(remote_side="OrgUnit.id")


class UserAccount(IDMixin, TimestampMixin, Base):
    __tablename__ = "user_account"
    __table_args__ = (
        Index("ix_user_account_email", "email"),
        Index("ix_user_account_phone_normalized", "phone_normalized"),
        Index(
            "uq_user_account_external_phone",
            "phone_normalized",
            unique=True,
            postgresql_where=text(
                "user_type = 'EXTERNAL_CUSTOMER' AND phone_normalized IS NOT NULL"
            ),
        ),
    )

    org_unit_id: Mapped[str] = mapped_column(ForeignKey("org_unit.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    user_type: Mapped[str] = mapped_column(String(50), nullable=False, default=UserType.EXTERNAL_CUSTOMER)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    phone_normalized: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=ResourceStatus.ACTIVE)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 登录凭证字段
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    password_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    token_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    org_unit: Mapped[OrgUnit] = relationship()

from datetime import datetime, timezone

from sqlalchemy import Computed, DateTime, ForeignKey, Index, Integer, String, Text
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
        # 「仅外部客户手机号唯一」：MySQL 不支持带 WHERE 的部分唯一索引，
        # 改用生成列——仅外部客户取 phone_normalized，其余为 NULL（唯一索引允许多个 NULL），
        # 再对生成列建普通唯一索引，由数据库层硬保证唯一性。
        Index("uq_user_account_external_phone", "external_phone_uk", unique=True),
    )

    org_unit_id: Mapped[str] = mapped_column(ForeignKey("org_unit.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    user_type: Mapped[str] = mapped_column(String(50), nullable=False, default=UserType.EXTERNAL_CUSTOMER)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    phone_normalized: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # 唯一约束专用生成列，不参与业务读写；业务查找仍使用 phone_normalized
    external_phone_uk: Mapped[str | None] = mapped_column(
        String(32),
        Computed(
            "(CASE WHEN user_type = 'EXTERNAL_CUSTOMER' THEN phone_normalized ELSE NULL END)",
            persisted=True,
        ),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=ResourceStatus.ACTIVE)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 登录凭证字段
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    password_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    token_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    org_unit: Mapped[OrgUnit] = relationship()

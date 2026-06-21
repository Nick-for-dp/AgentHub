from datetime import datetime, timezone

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column
from uuid6 import uuid7


def uuid_str() -> str:
    # 使用 UUIDv7（时间有序），缓解 MySQL InnoDB 聚簇索引下随机 UUID 主键的页分裂和写放大
    return str(uuid7())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class IDMixin:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )

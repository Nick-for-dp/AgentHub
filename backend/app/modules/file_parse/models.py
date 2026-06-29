from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import FileParseTaskStatus
from app.db.base import Base
from app.db.mixins import IDMixin, TimestampMixin


class FileParseTask(IDMixin, TimestampMixin, Base):
    """文件解析任务。

    解析任务是 Agent 调用的前置步骤，只保存单文件读取与章节推断结果，不写
    ``agent_invocation_record``。后续合同审查或风控任务消费解析结果时，才在对应
    invocation 的 ``snapshot.runtime.inputs`` 中引用本表 ID。
    """

    __tablename__ = "file_parse_task"
    __table_args__ = (
        Index("ix_file_parse_task_owner_created", "owner_org_unit_id", "created_at"),
        Index("ix_file_parse_task_created_by_created", "created_by", "created_at"),
        Index("ix_file_parse_task_status_created", "status", "created_at"),
    )

    owner_org_unit_id: Mapped[str | None] = mapped_column(
        ForeignKey("org_unit.id"),
        nullable=True,
    )
    created_by: Mapped[str | None] = mapped_column(ForeignKey("user_account.id"), nullable=True)
    api_key_id: Mapped[str | None] = mapped_column(ForeignKey("api_key.id"), nullable=True)
    source_uri: Mapped[str] = mapped_column(String(500), nullable=False)
    file_type: Mapped[str] = mapped_column(String(32), nullable=False)
    reader_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=FileParseTaskStatus.PENDING,
    )
    result_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

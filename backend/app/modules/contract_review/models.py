from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import ContractReviewTaskStatus
from app.db.base import Base
from app.db.mixins import IDMixin, TimestampMixin


class ContractReviewTask(IDMixin, TimestampMixin, Base):
    """合同审查业务任务。

    该表承载合同审查的业务状态、解析任务引用、规则集版本和最终判敏结果。真正调用
    Dify/LLM workflow 时才会创建或更新 ``agent_invocation_record``；仅创建、查询、
    取消业务任务不写 invocation。
    """

    __tablename__ = "contract_review_task"
    __table_args__ = (
        Index("ix_contract_review_task_owner_created", "owner_org_unit_id", "created_at"),
        Index("ix_contract_review_task_created_by_created", "created_by", "created_at"),
        Index("ix_contract_review_task_api_key_created", "api_key_id", "created_at"),
        Index("ix_contract_review_task_file_parse", "file_parse_task_id"),
        Index("ix_contract_review_task_status_created", "status", "created_at"),
    )

    owner_org_unit_id: Mapped[str | None] = mapped_column(
        ForeignKey("org_unit.id"),
        nullable=True,
    )
    created_by: Mapped[str | None] = mapped_column(ForeignKey("user_account.id"), nullable=True)
    api_key_id: Mapped[str | None] = mapped_column(ForeignKey("api_key.id"), nullable=True)
    agent_code: Mapped[str] = mapped_column(String(100), nullable=False)
    file_parse_task_id: Mapped[str] = mapped_column(
        ForeignKey("file_parse_task.id"),
        nullable=False,
    )
    contract_type: Mapped[str] = mapped_column(String(50), nullable=False, default="warehouse")
    counterparty_level: Mapped[str] = mapped_column(String(16), nullable=False)
    rule_set_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    callback_metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    invocation_record_id: Mapped[str | None] = mapped_column(
        ForeignKey("agent_invocation_record.id"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=ContractReviewTaskStatus.PENDING,
    )
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

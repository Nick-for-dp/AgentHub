"""调用记录数据访问层。

封装对 agent_invocation_record 表的查询操作。
支持按 Agent、状态、API Key、时间范围等多维筛选，以及分页。
"""

from datetime import datetime

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.modules.invocation.models import AgentInvocationRecord


class InvocationRepository:
    """调用记录 Repository。

    提供创建、查询（单条/列表/筛选分页）等数据库操作。
    """

    def __init__(self, db: Session):
        self.db = db

    def add_record(self, record: AgentInvocationRecord) -> AgentInvocationRecord:
        """写入新调用记录（通常在 Agent 调用开始时调用）。"""
        self.db.add(record)
        self.db.flush()
        return record

    def get_record(self, record_id: str) -> AgentInvocationRecord | None:
        """按主键查询单条调用记录。"""
        return self.db.get(AgentInvocationRecord, record_id)

    def list_records(
        self,
        agent_id: str | None = None,
        status: str | None = None,
        api_key_id: str | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[AgentInvocationRecord], int]:
        """分页查询调用记录列表，支持多维筛选。

        Args:
            agent_id:   按 Agent ID 精确筛选
            status:     按调用状态筛选（SUCCEEDED / FAILED / STREAMING / PENDING）
            api_key_id: 按调用使用的 API Key 筛选
            created_from: 创建时间起始（含）
            created_to:   创建时间截止（含）
            page:       页码（从 1 开始）
            page_size:  每页条数（1-100）

        Returns:
            (当前页记录列表, 符合条件的总记录数)
        """
        # 基础查询：从 agent_invocation_record 表中选取所有列
        stmt = select(AgentInvocationRecord)

        # ── 逐条件追加 WHERE 子句 ────────────────────────
        if agent_id:
            stmt = stmt.where(AgentInvocationRecord.agent_id == agent_id)
        if status:
            stmt = stmt.where(AgentInvocationRecord.status == status)
        if api_key_id:
            stmt = stmt.where(AgentInvocationRecord.api_key_id == api_key_id)
        if created_from:
            stmt = stmt.where(AgentInvocationRecord.created_at >= created_from)
        if created_to:
            stmt = stmt.where(AgentInvocationRecord.created_at <= created_to)

        # ── 查询总数（用于前端分页器显示"共 X 条"）───
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = self.db.scalar(count_stmt) or 0

        # ── 排序 + 分页 ───────────────────────────────
        # 默认按创建时间倒序（最新的在前）
        stmt = stmt.order_by(AgentInvocationRecord.created_at.desc())
        offset = (page - 1) * page_size
        stmt = stmt.limit(page_size).offset(offset)

        records = list(self.db.scalars(stmt))
        return records, total

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session
from uuid6 import uuid7

from app.core.exceptions import ConflictError
from app.integrations.langgraph_checkpoint.models import RiskGraphCheckpoint


class MySQLRiskCheckpointStore:
    """风控图的轻量 MySQL checkpoint adapter。"""

    def __init__(self, db: Session) -> None:
        self.db = db

    def put(
        self,
        *,
        task_id: str,
        thread_id: str,
        state: dict,
        next_node: str | None,
        expected_version: int | None = None,
    ) -> RiskGraphCheckpoint:
        from app.modules.risk_assessment.models import RiskAssessmentTask

        locked_task_id = self.db.scalar(
            select(RiskAssessmentTask.id)
            .where(RiskAssessmentTask.id == task_id)
            .with_for_update()
        )
        if locked_task_id is None:
            raise ConflictError("risk assessment task not found")
        latest = self.db.scalar(
            select(RiskGraphCheckpoint)
            .where(RiskGraphCheckpoint.thread_id == thread_id)
            .order_by(RiskGraphCheckpoint.version.desc())
            .limit(1)
            .with_for_update()
        )
        current_version = latest.version if latest else 0
        if expected_version is not None and expected_version != current_version:
            raise ConflictError("risk graph checkpoint version conflict")
        checkpoint = RiskGraphCheckpoint(
            task_id=task_id,
            thread_id=thread_id,
            checkpoint_id=str(uuid7()),
            version=current_version + 1,
            state=state,
            next_node=next_node,
        )
        self.db.add(checkpoint)
        self.db.flush()
        return checkpoint

    def get(self, checkpoint_id: str) -> RiskGraphCheckpoint | None:
        return self.db.scalar(
            select(RiskGraphCheckpoint).where(
                RiskGraphCheckpoint.checkpoint_id == checkpoint_id
            )
        )

    def get_latest(self, thread_id: str) -> RiskGraphCheckpoint | None:
        return self.db.scalar(
            select(RiskGraphCheckpoint)
            .where(RiskGraphCheckpoint.thread_id == thread_id)
            .order_by(RiskGraphCheckpoint.version.desc())
            .limit(1)
        )

    def list(self, thread_id: str) -> list[RiskGraphCheckpoint]:
        return list(
            self.db.scalars(
                select(RiskGraphCheckpoint)
                .where(RiskGraphCheckpoint.thread_id == thread_id)
                .order_by(RiskGraphCheckpoint.version)
            )
        )

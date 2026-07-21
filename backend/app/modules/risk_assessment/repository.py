from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.integrations.langgraph_checkpoint.models import RiskGraphCheckpoint
from app.modules.risk_assessment.models import (
    RiskAssessmentDocument,
    RiskAssessmentTask,
    RiskReviewEvent,
)


class RiskAssessmentRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add_task(self, task: RiskAssessmentTask) -> None:
        self.db.add(task)

    def get_task(self, task_id: str, *, for_update: bool = False) -> RiskAssessmentTask | None:
        statement = select(RiskAssessmentTask).where(RiskAssessmentTask.id == task_id)
        if for_update:
            statement = statement.with_for_update()
        return self.db.scalar(statement)

    def list_tasks(
        self,
        *,
        created_by: str,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[tuple[RiskAssessmentTask, int]], int]:
        filters = [RiskAssessmentTask.created_by == created_by]
        if status is not None:
            filters.append(RiskAssessmentTask.status == status)
        total = int(
            self.db.scalar(
                select(func.count()).select_from(RiskAssessmentTask).where(*filters)
            )
            or 0
        )
        document_count = (
            select(func.count(RiskAssessmentDocument.id))
            .where(RiskAssessmentDocument.task_id == RiskAssessmentTask.id)
            .correlate(RiskAssessmentTask)
            .scalar_subquery()
        )
        statement = (
            select(RiskAssessmentTask, document_count)
            .where(*filters)
            .order_by(
                RiskAssessmentTask.created_at.desc(),
                RiskAssessmentTask.id.desc(),
            )
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
        return [(row[0], int(row[1])) for row in self.db.execute(statement)], total

    def add_documents(self, documents: list[RiskAssessmentDocument]) -> None:
        self.db.add_all(documents)

    def get_document(self, document_id: str) -> RiskAssessmentDocument | None:
        return self.db.get(RiskAssessmentDocument, document_id)

    def list_documents(self, task_id: str) -> list[RiskAssessmentDocument]:
        statement = (
            select(RiskAssessmentDocument)
            .where(RiskAssessmentDocument.task_id == task_id)
            .order_by(RiskAssessmentDocument.document_order, RiskAssessmentDocument.id)
        )
        return list(self.db.scalars(statement))

    def add_review_event(self, event: RiskReviewEvent) -> None:
        self.db.add(event)

    def get_review_event(self, event_id: str) -> RiskReviewEvent | None:
        return self.db.get(RiskReviewEvent, event_id)

    def list_review_events(self, task_id: str) -> list[RiskReviewEvent]:
        statement = (
            select(RiskReviewEvent)
            .where(RiskReviewEvent.task_id == task_id)
            .order_by(RiskReviewEvent.created_at, RiskReviewEvent.id)
        )
        return list(self.db.scalars(statement))

    def add_checkpoint(self, checkpoint: RiskGraphCheckpoint) -> None:
        self.db.add(checkpoint)

    def get_checkpoint(self, checkpoint_id: str) -> RiskGraphCheckpoint | None:
        return self.db.scalar(
            select(RiskGraphCheckpoint).where(
                RiskGraphCheckpoint.checkpoint_id == checkpoint_id
            )
        )

    def get_latest_checkpoint(self, thread_id: str) -> RiskGraphCheckpoint | None:
        return self.db.scalar(
            select(RiskGraphCheckpoint)
            .where(RiskGraphCheckpoint.thread_id == thread_id)
            .order_by(RiskGraphCheckpoint.version.desc())
            .limit(1)
        )

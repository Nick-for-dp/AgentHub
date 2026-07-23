from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.core.enums import (
    AgentType,
    FileParseTaskStatus,
    InvocationStatus,
    RiskAssessmentTaskStatus,
    RiskReviewTargetKind,
)
from app.core.exceptions import BadRequestError, ConflictError, ForbiddenError, NotFoundError
from app.integrations.object_storage import (
    FileStorage,
    create_file_storage,
    parse_storage_uri,
)
from app.modules.auth.schemas import AuthenticatedSubject
from app.modules.file_parse.models import FileParseTask
from app.modules.invocation.models import AgentInvocationRecord
from app.modules.invocation.schemas import InvocationRecordFinish
from app.modules.invocation.service import InvocationService
from app.modules.risk_assessment.models import (
    RiskAssessmentDocument,
    RiskAssessmentTask,
    RiskReviewEvent,
)
from app.modules.risk_assessment.overview import BusinessOverviewProjector
from app.modules.risk_assessment.repository import RiskAssessmentRepository
from app.modules.risk_assessment.schemas import (
    RiskAssessmentDocumentRead,
    RiskAssessmentDocumentAccessRead,
    RiskAssessmentTaskCreate,
    RiskAssessmentTaskPageRead,
    RiskAssessmentTaskRead,
    RiskAssessmentTaskSummaryRead,
    RiskReviewEventRead,
    RiskReviewSubmit,
)


class RiskAssessmentService:
    def __init__(self, db: Session, *, storage: FileStorage | None = None) -> None:
        self.db = db
        self.repository = RiskAssessmentRepository(db)
        self.storage = storage
        self.overview_projector = BusinessOverviewProjector()

    def create_task(
        self,
        *,
        payload: RiskAssessmentTaskCreate,
        subject: AuthenticatedSubject,
    ) -> RiskAssessmentTask:
        self._assert_internal_cookie_subject(subject)
        parse_tasks: list[FileParseTask] = []
        for item in payload.documents:
            parse_task = self.db.get(FileParseTask, item.file_parse_task_id)
            if parse_task is None:
                raise NotFoundError("file parse task not found")
            if not self._is_subject_owner(parse_task, subject):
                raise ForbiddenError("permission denied")
            if parse_task.status != FileParseTaskStatus.SUCCEEDED:
                raise ConflictError("file parse task must be succeeded")
            if not parse_task.original_filename:
                raise ConflictError("file parse task original filename is required; re-upload file")
            parse_tasks.append(parse_task)

        task = RiskAssessmentTask(
            owner_org_unit_id=subject.org_unit_id,
            created_by=subject.user_id,
            api_key_id=None,
            agent_code=payload.agent_code,
            business_code=payload.business_code,
            status=RiskAssessmentTaskStatus.PENDING,
            versions={},
        )
        self.repository.add_task(task)
        self.db.flush()
        documents = [
            RiskAssessmentDocument(
                task_id=task.id,
                file_parse_task_id=parse_task.id,
                original_filename=parse_task.original_filename or "",
                declared_document_type=item.declared_document_type,
                document_order=index,
                type_validation_warnings=[],
            )
            for index, (item, parse_task) in enumerate(zip(payload.documents, parse_tasks))
        ]
        self.repository.add_documents(documents)
        self.db.commit()
        self.db.refresh(task)
        return task

    def get_task(
        self,
        *,
        task_id: str,
        subject: AuthenticatedSubject,
        for_update: bool = False,
    ) -> RiskAssessmentTask:
        self._assert_internal_cookie_subject(subject)
        task = self.repository.get_task(task_id, for_update=for_update)
        if task is None:
            raise NotFoundError("risk assessment task not found")
        if not self._is_subject_owner(task, subject):
            raise ForbiddenError("permission denied")
        return task

    def list_tasks(
        self,
        *,
        subject: AuthenticatedSubject,
        page: int = 1,
        page_size: int = 20,
        status: RiskAssessmentTaskStatus | None = None,
    ) -> RiskAssessmentTaskPageRead:
        self._assert_internal_cookie_subject(subject)
        rows, total = self.repository.list_tasks(
            created_by=subject.user_id or "",
            status=status.value if status is not None else None,
            page=page,
            page_size=page_size,
        )
        return RiskAssessmentTaskPageRead(
            items=[
                RiskAssessmentTaskSummaryRead(
                    id=task.id,
                    business_code=task.business_code,
                    status=task.status,
                    current_node=task.current_node,
                    document_count=document_count,
                    error_message=task.error_message,
                    created_at=task.created_at,
                    updated_at=task.updated_at,
                    finished_at=task.finished_at,
                )
                for task, document_count in rows
            ],
            total=total,
            page=page,
            page_size=page_size,
        )

    def get_document_access(
        self,
        *,
        task_id: str,
        document_id: str,
        subject: AuthenticatedSubject,
    ) -> RiskAssessmentDocumentAccessRead:
        task = self.get_task(task_id=task_id, subject=subject)
        document = self.repository.get_document(document_id)
        if document is None or document.task_id != task.id:
            raise NotFoundError("risk assessment document not found")
        parse_task = self.db.get(FileParseTask, document.file_parse_task_id)
        if parse_task is None:
            raise NotFoundError("file parse task not found")
        if not self._is_subject_owner(parse_task, subject):
            raise ForbiddenError("permission denied")
        bucket, object_key = parse_storage_uri(parse_task.source_uri)
        storage = self.storage or create_file_storage()
        presigned = storage.create_presigned_download_url(
            bucket=bucket,
            object_key=object_key,
        )
        file_type = parse_task.file_type
        original_filename = document.original_filename
        return RiskAssessmentDocumentAccessRead(
            access_url=presigned.url,
            method=presigned.method,
            headers=presigned.headers,
            expires_seconds=presigned.expires_seconds,
            original_filename=original_filename,
            file_type=file_type,
        )

    async def execute_task(
        self,
        *,
        task_id: str,
        subject: AuthenticatedSubject,
        request_id: str | None = None,
    ) -> RiskAssessmentTask:
        task = self.get_task(task_id=task_id, subject=subject)
        agent, handler = self._load_risk_handler(task.agent_code)

        from app.modules.agent.runtime import AgentRuntimeService
        from app.modules.agent.task_handlers import TaskContext

        return await handler.execute(
            TaskContext(
                db=self.db,
                subject=subject,
                task_id=task.id,
                agent=agent,
                runtime_service=AgentRuntimeService(),
                request_id=request_id,
            )
        )

    def to_read(self, task: RiskAssessmentTask) -> RiskAssessmentTaskRead:
        documents = [
            RiskAssessmentDocumentRead.model_validate(document)
            for document in self.repository.list_documents(task.id)
        ]
        events = [
            RiskReviewEventRead.model_validate(event)
            for event in self.repository.list_review_events(task.id)
        ]
        result = task.result_snapshot
        review_context = (
            result if task.status == RiskAssessmentTaskStatus.WAITING_REVIEW else None
        )
        business_overview = self.overview_projector.project(
            business_code=task.business_code,
            generated_at=task.updated_at,
            result=result,
            review_events=events,
        )
        return RiskAssessmentTaskRead(
            id=task.id,
            owner_org_unit_id=task.owner_org_unit_id,
            created_by=task.created_by,
            status=task.status,
            agent_code=task.agent_code,
            business_code=task.business_code,
            graph_thread_id=task.graph_thread_id,
            checkpoint_version=task.checkpoint_version,
            current_node=task.current_node,
            invocation_record_id=task.invocation_record_id,
            versions=task.versions or {},
            documents=documents,
            result=result if task.status != RiskAssessmentTaskStatus.WAITING_REVIEW else None,
            review_context=review_context,
            review_events=events,
            business_overview=business_overview,
            error_message=task.error_message,
            created_at=task.created_at,
            updated_at=task.updated_at,
            finished_at=task.finished_at,
        )

    def accept_review(
        self,
        *,
        task_id: str,
        payload: RiskReviewSubmit,
        subject: AuthenticatedSubject,
    ) -> tuple[RiskAssessmentTask, RiskReviewEvent]:
        task = self.get_task(task_id=task_id, subject=subject, for_update=True)
        if task.status != RiskAssessmentTaskStatus.WAITING_REVIEW:
            raise ConflictError("only waiting risk assessment task accepts review")
        if task.checkpoint_version != payload.checkpoint_version:
            raise ConflictError("risk graph checkpoint version conflict")
        result = task.result_snapshot or {}
        review_item = next(
            (
                item
                for item in result.get("review_items", [])
                if item.get("id") == payload.review_item_id and not item.get("is_resolved")
            ),
            None,
        )
        if review_item is None:
            raise ConflictError("review item is not active")
        if (
            review_item.get("target_kind") != payload.target_kind.value
            or review_item.get("target_code") != payload.target_code
        ):
            raise ConflictError("review target does not match active item")

        before, alternatives, sources = self._review_source(result, review_item)
        after_value: dict[str, Any] | None
        if payload.target_kind == RiskReviewTargetKind.DOCUMENT_TYPE:
            if payload.action != "CONFIRM_DECLARED_TYPE":
                raise BadRequestError("document type cannot be changed in the current task")
            document = next(
                item
                for item in result.get("documents", [])
                if item.get("id") == payload.target_code
            )
            after_value = {"value": document["declared_document_type"]}
        else:
            if payload.action not in {"SELECT_VALUE", "CORRECT_VALUE", "MARK_MISSING"}:
                raise BadRequestError("unsupported field review action")
            if payload.action == "SELECT_VALUE" and payload.value not in alternatives:
                raise BadRequestError("selected value is not an active alternative")
            after_value = {"value": None if payload.action == "MARK_MISSING" else payload.value}

        event = RiskReviewEvent(
            task_id=task.id,
            review_item_id=payload.review_item_id,
            target_kind=payload.target_kind,
            target_code=payload.target_code,
            before_value=before,
            alternatives=alternatives,
            after_value=after_value,
            action=payload.action,
            reason=payload.reason.strip(),
            actor_user_id=subject.user_id,
            sources=sources,
            checkpoint_version=payload.checkpoint_version,
        )
        self.repository.add_review_event(event)
        task.status = RiskAssessmentTaskStatus.RUNNING
        task.current_node = "apply_human_review"
        self.db.add(task)
        self.db.commit()
        self.db.refresh(event)
        self.db.refresh(task)
        return task, event

    async def submit_review(
        self,
        *,
        task_id: str,
        payload: RiskReviewSubmit,
        subject: AuthenticatedSubject,
        request_id: str | None = None,
    ) -> RiskAssessmentTask:
        current = self.get_task(task_id=task_id, subject=subject)
        agent, handler = self._load_risk_handler(current.agent_code)
        task, event = self.accept_review(
            task_id=task_id,
            payload=payload,
            subject=subject,
        )

        from app.modules.agent.runtime import AgentRuntimeService
        from app.modules.agent.task_handlers import TaskContext

        return await handler.resume(
            TaskContext(
                db=self.db,
                subject=subject,
                task_id=task.id,
                agent=agent,
                runtime_service=AgentRuntimeService(),
                request_id=request_id,
            ),
            {
                "review_event_id": event.id,
                "checkpoint_version": payload.checkpoint_version,
            },
        )

    def cancel_task(
        self,
        *,
        task_id: str,
        subject: AuthenticatedSubject,
    ) -> RiskAssessmentTask:
        task = self.get_task(task_id=task_id, subject=subject, for_update=True)
        if task.status in {
            RiskAssessmentTaskStatus.SUCCEEDED,
            RiskAssessmentTaskStatus.FAILED,
            RiskAssessmentTaskStatus.CANCELLED,
        }:
            raise ConflictError("terminal risk assessment task cannot be cancelled")
        task.status = RiskAssessmentTaskStatus.CANCELLED
        task.error_message = "USER_CANCELLED"
        task.finished_at = datetime.now(timezone.utc)
        if task.invocation_record_id:
            invocation = self.db.get(AgentInvocationRecord, task.invocation_record_id)
            if invocation is not None and invocation.finished_at is None:
                InvocationService(self.db).finish_record(
                    invocation.id,
                    InvocationRecordFinish(
                        status=InvocationStatus.FAILED,
                        error_code="USER_CANCELLED",
                        error_message="risk assessment task cancelled by user",
                        snapshot=invocation.snapshot or {},
                    ),
                )
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return task

    def soft_delete_task(
        self,
        *,
        task_id: str,
        subject: AuthenticatedSubject,
    ) -> None:
        """隐藏用户任务，同时保留任务、文档、复核和调用记录用于审计。"""
        task = self.get_task(task_id=task_id, subject=subject, for_update=True)
        if task.status not in {
            RiskAssessmentTaskStatus.SUCCEEDED,
            RiskAssessmentTaskStatus.FAILED,
            RiskAssessmentTaskStatus.CANCELLED,
        }:
            raise ConflictError("only terminal risk assessment task can be deleted")
        task.deleted_at = datetime.now(timezone.utc)
        task.deleted_by_user_id = subject.user_id
        self.db.add(task)
        self.db.commit()

    @staticmethod
    def _review_source(
        result: dict[str, Any], review_item: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, list[Any], list[dict[str, Any]]]:
        if review_item.get("target_kind") == RiskReviewTargetKind.FIELD.value:
            fact = (result.get("document_facts") or {}).get(review_item["target_code"]) or {}
            return (
                {"value": fact.get("value")},
                list(fact.get("alternatives") or []),
                list(fact.get("sources") or []),
            )
        return (
            {"value": review_item.get("before")},
            [],
            list(review_item.get("sources") or []),
        )

    @staticmethod
    def _assert_internal_cookie_subject(subject: AuthenticatedSubject) -> None:
        if (
            subject.api_key_id
            or subject.caller_type.upper() != "USER"
            or not subject.user_id
            or not subject.org_unit_id
        ):
            raise ForbiddenError("risk assistant requires an authenticated internal user")

    @staticmethod
    def _is_subject_owner(resource, subject: AuthenticatedSubject) -> bool:
        if getattr(resource, "created_by", None) and subject.user_id:
            return resource.created_by == subject.user_id
        if getattr(resource, "owner_org_unit_id", None) and subject.org_unit_id:
            return resource.owner_org_unit_id == subject.org_unit_id
        return False

    def _load_risk_handler(self, agent_code: str):
        from app.modules.agent.service import AgentService
        from app.modules.agent.task_handlers import get_task_handler_registry

        agent = AgentService(self.db).get_agent_by_code(agent_code)
        raw_type = getattr(agent, "type", None)
        agent_type = raw_type.value if isinstance(raw_type, AgentType) else str(raw_type)
        if agent_type != AgentType.RISK_ASSISTANT.value:
            raise ConflictError("agent type must be RISK_ASSISTANT")
        return agent, get_task_handler_registry().select(agent)

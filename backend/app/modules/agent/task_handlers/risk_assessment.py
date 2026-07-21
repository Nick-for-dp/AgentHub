from __future__ import annotations

from datetime import datetime, timezone
from time import perf_counter
from uuid import uuid4

from uuid6 import uuid7

from app.core.enums import (
    AgentType,
    CallerType,
    InvocationStatus,
    OperationType,
    RiskAssessmentTaskStatus,
)
from app.core.exceptions import ConflictError, UnsupportedRuntimeError
from app.integrations.langgraph_checkpoint.mysql import MySQLRiskCheckpointStore
from app.integrations.object_storage import create_file_storage
from app.modules.agent.task_handlers import TaskContext, TaskHandler
from app.modules.agent.task_handlers.pipeline import SuspendedResult
from app.modules.invocation.models import AgentInvocationRecord
from app.modules.invocation.schemas import InvocationRecordCreate, InvocationRecordFinish
from app.modules.invocation.service import InvocationService
from app.modules.risk_assessment.extraction.access import assert_risk_document_extraction_access
from app.modules.risk_assessment.extraction.provider_factory import (
    create_document_extraction_provider,
)
from app.modules.risk_assessment.extraction.service import DocumentExtractionService
from app.modules.risk_assessment.graph.executor import RiskGraphExecutor
from app.modules.risk_assessment.graph.state import RiskGraphContext
from app.modules.risk_assessment.models import RiskAssessmentTask
from app.modules.risk_assessment.service import RiskAssessmentService


class RiskAssessmentTaskHandler(TaskHandler):
    def __init__(
        self,
        *,
        graph_executor: RiskGraphExecutor | None = None,
        extraction_service: DocumentExtractionService | None = None,
    ) -> None:
        self.graph_executor = graph_executor or RiskGraphExecutor()
        self._extraction_service = extraction_service

    async def execute(self, ctx: TaskContext) -> RiskAssessmentTask:
        self.prepare_execution(ctx)
        self.begin_execution(ctx)
        started_at = perf_counter()
        try:
            result = await self.graph_executor.execute(
                task_id=ctx.task_id,
                thread_id=ctx.state["task"].graph_thread_id,
                context=self._graph_context(ctx, require_extraction=True),
            )
        except Exception as exc:
            return self.finalize_failure(
                ctx,
                exc,
                latency_ms=int((perf_counter() - started_at) * 1000),
            )
        latency_ms = int((perf_counter() - started_at) * 1000)
        if result.is_suspended:
            return self.finalize_suspended(
                ctx,
                SuspendedResult(
                    reason="WAITING_REVIEW",
                    business_result=result.state.get("result_snapshot", {}),
                    snapshot_runtime_extra={
                        "execution_state": "WAITING_REVIEW",
                        "graph_thread_id": ctx.state["task"].graph_thread_id,
                    },
                ),
            )
        return self.finalize_success(ctx, result.state, latency_ms=latency_ms)

    async def resume(self, ctx: TaskContext, resume_payload: dict) -> RiskAssessmentTask:
        self.prepare_resume(ctx)
        started_at = perf_counter()
        try:
            result = await self.graph_executor.resume(
                task_id=ctx.task_id,
                thread_id=ctx.state["task"].graph_thread_id,
                review_event_id=resume_payload["review_event_id"],
                expected_version=resume_payload["checkpoint_version"],
                context=self._graph_context(ctx, require_extraction=False),
            )
        except Exception as exc:
            return self.finalize_failure(
                ctx,
                exc,
                latency_ms=int((perf_counter() - started_at) * 1000),
            )
        latency_ms = int((perf_counter() - started_at) * 1000)
        if result.is_suspended:
            return self.finalize_suspended(
                ctx,
                SuspendedResult(
                    reason="WAITING_REVIEW",
                    business_result=result.state.get("result_snapshot", {}),
                    snapshot_runtime_extra={"execution_state": "WAITING_REVIEW"},
                ),
            )
        return self.finalize_success(ctx, result.state, latency_ms=latency_ms)

    def prepare_execution(self, ctx: TaskContext) -> None:
        assert_risk_document_extraction_access(agent=ctx.agent, subject=ctx.subject)
        service = RiskAssessmentService(ctx.db)
        task = service.get_task(task_id=ctx.task_id, subject=ctx.subject, for_update=True)
        if task.status != RiskAssessmentTaskStatus.PENDING:
            raise ConflictError("only pending risk assessment task can be executed")
        self._assert_agent(ctx.agent)
        ctx.state.update(
            {
                "task": task,
                "service": service,
                "repository": service.repository,
                "invocation_service": InvocationService(ctx.db),
            }
        )

    def prepare_resume(self, ctx: TaskContext) -> None:
        assert_risk_document_extraction_access(agent=ctx.agent, subject=ctx.subject)
        service = RiskAssessmentService(ctx.db)
        task = service.get_task(task_id=ctx.task_id, subject=ctx.subject)
        if task.status != RiskAssessmentTaskStatus.RUNNING or task.current_node != "apply_human_review":
            raise ConflictError("risk assessment task is not ready to resume")
        if not task.invocation_record_id or not task.graph_thread_id:
            raise ConflictError("risk assessment resume state is incomplete")
        self._assert_agent(ctx.agent)
        invocation = ctx.db.get(AgentInvocationRecord, task.invocation_record_id)
        if invocation is None or invocation.finished_at is not None:
            raise ConflictError("risk assessment invocation cannot be resumed")
        ctx.state.update(
            {
                "task": task,
                "service": service,
                "repository": service.repository,
                "invocation": invocation,
                "invocation_service": InvocationService(ctx.db),
            }
        )

    def begin_execution(self, ctx: TaskContext) -> None:
        task: RiskAssessmentTask = ctx.state["task"]
        documents = ctx.state["repository"].list_documents(task.id)
        invocation_payload = InvocationRecordCreate(
            request_id=ctx.request_id or str(uuid4()),
            agent_id=ctx.agent.id,
            org_unit_id=ctx.subject.org_unit_id,
            user_id=ctx.subject.user_id,
            api_key_id=None,
            caller_type=CallerType.USER,
            source_channel="INTERNAL_WEB",
            operation_type=OperationType.RISK_ASSESSMENT,
            input={
                "risk_assessment_task_id": task.id,
                "business_code": task.business_code,
                "documents": [
                    {
                        "file_parse_task_id": item.file_parse_task_id,
                        "declared_document_type": item.declared_document_type,
                    }
                    for item in documents
                ],
            },
            stream_mode=False,
        )
        invocation = AgentInvocationRecord(**invocation_payload.model_dump())
        ctx.db.add(invocation)
        ctx.db.flush()
        task.invocation_record_id = invocation.id
        task.graph_thread_id = str(uuid7())
        task.status = RiskAssessmentTaskStatus.RUNNING
        task.current_node = "load_file_parse_results"
        task.error_message = None
        task.finished_at = None
        ctx.db.add(task)
        ctx.db.commit()
        ctx.db.refresh(task)
        ctx.state["invocation"] = invocation

    def finalize_suspended(
        self,
        ctx: TaskContext,
        suspended: SuspendedResult,
    ) -> RiskAssessmentTask:
        task: RiskAssessmentTask = ctx.state["task"]
        ctx.state["invocation_service"].update_pending_record(
            task.invocation_record_id,
            output=suspended.business_result,
            snapshot_runtime_extra={
                **suspended.snapshot_runtime_extra,
                "checkpoint_id": task.current_checkpoint_id,
                "checkpoint_version": task.checkpoint_version,
                "current_node": task.current_node,
            },
        )
        ctx.db.refresh(task)
        return task

    def finalize_success(
        self,
        ctx: TaskContext,
        state: dict,
        *,
        latency_ms: int,
    ) -> RiskAssessmentTask:
        task: RiskAssessmentTask = ctx.state["task"]
        invocation: AgentInvocationRecord = ctx.state["invocation"]
        result = state.get("result_snapshot", task.result_snapshot or {})
        ctx.state["invocation_service"].finish_record(
            invocation.id,
            InvocationRecordFinish(
                output=result,
                status=InvocationStatus.SUCCEEDED,
                latency_ms=latency_ms,
                snapshot=self._snapshot(task, execution_state="SUCCEEDED"),
            ),
        )
        task.result_snapshot = result
        task.status = RiskAssessmentTaskStatus.SUCCEEDED
        task.current_node = "finalize_document_result"
        task.error_message = None
        task.finished_at = datetime.now(timezone.utc)
        return self._save(ctx, task)

    def finalize_failure(
        self,
        ctx: TaskContext,
        exc: Exception,
        *,
        latency_ms: int,
    ) -> RiskAssessmentTask:
        task: RiskAssessmentTask = ctx.state["task"]
        invocation: AgentInvocationRecord = ctx.state["invocation"]
        ctx.state["invocation_service"].finish_record(
            invocation.id,
            InvocationRecordFinish(
                status=InvocationStatus.FAILED,
                error_code=exc.__class__.__name__,
                error_message=str(exc),
                latency_ms=latency_ms,
                snapshot=self._snapshot(task, execution_state="FAILED"),
            ),
        )
        task.status = RiskAssessmentTaskStatus.FAILED
        task.error_message = str(exc)
        task.finished_at = datetime.now(timezone.utc)
        return self._save(ctx, task)

    def _graph_context(
        self,
        ctx: TaskContext,
        *,
        require_extraction: bool,
    ) -> RiskGraphContext:
        extraction_service = self._extraction_service
        if extraction_service is None and require_extraction:
            extraction_service = DocumentExtractionService(
                provider=create_document_extraction_provider(),
                storage=create_file_storage(),
            )
        return RiskGraphContext(
            db=ctx.db,
            repository=ctx.state["repository"],
            extraction_service=extraction_service,
            checkpoint_store=MySQLRiskCheckpointStore(ctx.db),
        )

    @staticmethod
    def _assert_agent(agent) -> None:
        raw_type = getattr(agent, "type", None)
        agent_type = raw_type.value if isinstance(raw_type, AgentType) else str(raw_type)
        if agent_type != AgentType.RISK_ASSISTANT.value:
            raise UnsupportedRuntimeError("agent type must be RISK_ASSISTANT")

    @staticmethod
    def _snapshot(task: RiskAssessmentTask, *, execution_state: str) -> dict:
        return {
            "retrieval": {},
            "model": {},
            "runtime": {
                "execution_state": execution_state,
                "risk_assessment_task_id": task.id,
                "graph_thread_id": task.graph_thread_id,
                "checkpoint_id": task.current_checkpoint_id,
                "checkpoint_version": task.checkpoint_version,
                "current_node": task.current_node,
            },
        }

    @staticmethod
    def _save(ctx: TaskContext, task: RiskAssessmentTask) -> RiskAssessmentTask:
        ctx.db.add(task)
        ctx.db.commit()
        ctx.db.refresh(task)
        return task

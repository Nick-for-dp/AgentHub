from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from app.core.enums import RiskAssessmentTaskStatus
from app.core.exceptions import ConflictError
from app.modules.risk_assessment.graph.builder import RiskAssessmentGraph
from app.modules.risk_assessment.graph.state import RiskGraphContext, RiskGraphState


@dataclass(frozen=True)
class RiskGraphExecutionResult:
    state: RiskGraphState
    is_suspended: bool


class RiskGraphExecutor:
    def __init__(self, *, graph: RiskAssessmentGraph | None = None) -> None:
        self.graph = graph or RiskAssessmentGraph()

    async def execute(
        self,
        *,
        task_id: str,
        thread_id: str,
        context: RiskGraphContext,
    ) -> RiskGraphExecutionResult:
        state = await self.graph.invoke(
            RiskGraphState(
                task_id=task_id,
                thread_id=thread_id,
                checkpoint_version=0,
                warnings=[],
            ),
            context=context,
        )
        state.pop("__interrupt__", None)
        return self._persist_outcome(state=state, context=context, expected_version=0)

    async def resume(
        self,
        *,
        task_id: str,
        thread_id: str,
        review_event_id: str,
        expected_version: int,
        context: RiskGraphContext,
    ) -> RiskGraphExecutionResult:
        task = context.repository.get_task(task_id, for_update=True)
        is_waiting = task is not None and task.status == RiskAssessmentTaskStatus.WAITING_REVIEW
        is_review_accepted = (
            task is not None
            and task.status == RiskAssessmentTaskStatus.RUNNING
            and task.current_node == "apply_human_review"
        )
        if not (is_waiting or is_review_accepted):
            raise ConflictError("only waiting risk assessment task can be resumed")
        if task.checkpoint_version != expected_version:
            raise ConflictError("risk graph checkpoint version conflict")
        checkpoint = context.checkpoint_store.get_latest(thread_id)
        if checkpoint is None or checkpoint.task_id != task_id:
            raise ConflictError("risk graph checkpoint not found")
        if checkpoint.version != expected_version:
            raise ConflictError("risk graph checkpoint version conflict")
        resumed_state = cast(RiskGraphState, dict(checkpoint.state))
        resumed_state.update(
            {
                "task_id": task_id,
                "thread_id": thread_id,
                "checkpoint_version": checkpoint.version,
                "review_event_id": review_event_id,
            }
        )
        state = await self.graph.invoke(resumed_state, context=context)
        state.pop("__interrupt__", None)
        return self._persist_outcome(
            state=state,
            context=context,
            expected_version=checkpoint.version,
        )

    @staticmethod
    def _persist_outcome(
        *,
        state: RiskGraphState,
        context: RiskGraphContext,
        expected_version: int,
    ) -> RiskGraphExecutionResult:
        task = context.repository.get_task(state["task_id"], for_update=True)
        if task is None:
            raise ConflictError("risk assessment task not found")
        is_suspended = state.get("execution_state") == "WAITING_REVIEW"
        if is_suspended:
            checkpoint_state = {
                key: value
                for key, value in state.items()
                if key not in {"result_snapshot", "review_event_id", "__interrupt__"}
            }
            checkpoint = context.checkpoint_store.put(
                task_id=task.id,
                thread_id=state["thread_id"],
                state=checkpoint_state,
                next_node="apply_human_review",
                expected_version=expected_version,
            )
            task.status = RiskAssessmentTaskStatus.WAITING_REVIEW
            task.current_checkpoint_id = checkpoint.checkpoint_id
            task.checkpoint_version = checkpoint.version
            task.current_node = "route_review"
        else:
            task.status = RiskAssessmentTaskStatus.RUNNING
            task.current_node = "finalize_document_result"
        context.db.add(task)
        context.db.commit()
        context.db.refresh(task)
        return RiskGraphExecutionResult(state=state, is_suspended=is_suspended)

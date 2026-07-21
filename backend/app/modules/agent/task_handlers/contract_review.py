"""合同审查 TaskHandler：三阶段组装与任务/invocation finalize。

输入构造、runtime core、规则与高亮等领域步骤位于
``app.modules.contract_review.steps``。本类只负责：

1. 使用已鉴权 ``ctx.subject`` 做 scope、归属、状态与 agent.type 校验；
2. 声明有序的前处理 / 核心 / 后处理步骤；
3. 统一写入任务状态和 invocation 的 retrieval/model/runtime 三段快照。

本类不解析 API Key，也不直接依赖 ``app.integrations.dify``。
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from time import perf_counter
from uuid import uuid4

from app.core.enums import (
    AgentType,
    CallerType,
    ContractReviewTaskStatus,
    InvocationStatus,
    OperationType,
)
from app.core.exceptions import ConflictError, UnsupportedRuntimeError
from app.modules.agent.runtime import AgentRuntimeService
from app.modules.agent.task_handlers import TaskContext, TaskHandler
from app.modules.agent.task_handlers.pipeline import (
    CoreResult,
    PostprocessResult,
    PreprocessResult,
    TaskCoreStep,
    TaskPostprocessStep,
    TaskPreprocessStep,
    run_pipeline,
    run_postprocess_steps,
    run_preprocess_steps,
)
from app.modules.contract_review.models import ContractReviewTask
from app.modules.contract_review.rules import CreditClauseRuleEngine
from app.modules.contract_review.service import (
    ContractReviewService,
    assert_contract_review_scope,
)
from app.modules.contract_review.steps import (
    ContractReviewPostprocessStep,
    ContractReviewPreprocessStep,
    ContractReviewWorkflowCoreStep,
)
from app.modules.invocation.models import AgentInvocationRecord
from app.modules.invocation.schemas import InvocationRecordCreate, InvocationRecordFinish
from app.modules.invocation.service import InvocationService


class ContractReviewTaskHandler(TaskHandler):
    """合同审查任务型 handler。

    扩展方式：通过 ``preprocess_steps`` / ``postprocess_steps`` 替换完整有序列表，
    或通过 ``additional_*_steps`` 在默认主步骤之后增补步骤；endpoint 无需修改。
    合同规则和高亮是必需后处理，失败会使任务与 invocation 同时进入 FAILED。
    """

    def __init__(
        self,
        *,
        runtime_service: AgentRuntimeService | None = None,
        rule_engine: CreditClauseRuleEngine | None = None,
        preprocess_steps: Sequence[TaskPreprocessStep] | None = None,
        core_step: TaskCoreStep | None = None,
        postprocess_steps: Sequence[TaskPostprocessStep] | None = None,
        additional_preprocess_steps: Sequence[TaskPreprocessStep] = (),
        additional_postprocess_steps: Sequence[TaskPostprocessStep] = (),
    ) -> None:
        self._injected_runtime = runtime_service
        base_preprocess = (
            tuple(preprocess_steps)
            if preprocess_steps is not None
            else (ContractReviewPreprocessStep(),)
        )
        base_postprocess = (
            tuple(postprocess_steps)
            if postprocess_steps is not None
            else (ContractReviewPostprocessStep(rule_engine=rule_engine),)
        )
        self._preprocess_steps = (*base_preprocess, *additional_preprocess_steps)
        self._core_step = core_step or ContractReviewWorkflowCoreStep()
        self._postprocess_steps = (*base_postprocess, *additional_postprocess_steps)
        if not self._preprocess_steps:
            raise ValueError("task handler requires at least one preprocess step")
        if not self._postprocess_steps:
            raise ValueError("task handler requires at least one postprocess step")

    @property
    def preprocess_steps(self) -> Sequence[TaskPreprocessStep]:
        return self._preprocess_steps

    @property
    def core_step(self) -> TaskCoreStep:
        return self._core_step

    @property
    def postprocess_steps(self) -> Sequence[TaskPostprocessStep]:
        return self._postprocess_steps

    def preprocess(self, ctx: TaskContext) -> PreprocessResult:
        """顺序执行全部前处理步骤。"""
        return run_preprocess_steps(self.preprocess_steps, ctx)

    async def core(self, ctx: TaskContext, pre: PreprocessResult) -> CoreResult:
        """执行唯一核心处理步骤。"""
        return await self.core_step.run(ctx, pre)

    def postprocess(
        self,
        ctx: TaskContext,
        pre: PreprocessResult,
        core: CoreResult,
    ) -> PostprocessResult:
        """顺序执行全部后处理步骤。"""
        return run_postprocess_steps(self.postprocess_steps, ctx, pre, core)

    async def execute(self, ctx: TaskContext) -> ContractReviewTask:
        """执行合同审查状态机与三阶段流水线。"""
        self.prepare_execution(ctx)
        self.begin_execution(ctx)
        started_at = perf_counter()
        try:
            pre, core, post = await run_pipeline(
                preprocess=self.preprocess,
                core=self.core,
                postprocess=self.postprocess,
                ctx=ctx,
            )
        except Exception as exc:
            latency_ms = int((perf_counter() - started_at) * 1000)
            return self.finalize_failure(ctx, exc, latency_ms=latency_ms)

        latency_ms = int((perf_counter() - started_at) * 1000)
        return self.finalize_success(
            ctx,
            pre,
            core,
            post,
            latency_ms=latency_ms,
        )

    def prepare_execution(self, ctx: TaskContext) -> None:
        """在 runtime 前完成 scope、归属、PENDING 与 agent.type 校验。"""
        if self._injected_runtime is not None:
            ctx.runtime_service = self._injected_runtime

        assert_contract_review_scope(ctx.subject)
        service = ContractReviewService(ctx.db)
        task = service.get_task(task_id=ctx.task_id, subject=ctx.subject)
        if task.status != ContractReviewTaskStatus.PENDING:
            raise ConflictError("only pending contract review task can be executed")
        self._assert_contract_review_agent(ctx.agent)

        ctx.state["task"] = task
        ctx.state["contract_review_service"] = service
        ctx.state["invocation_service"] = InvocationService(ctx.db)

    def begin_execution(self, ctx: TaskContext) -> None:
        """创建 invocation，并把业务任务切换为 RUNNING。"""
        task: ContractReviewTask = ctx.state["task"]
        invocation_service: InvocationService = ctx.state["invocation_service"]
        subject = ctx.subject
        agent = ctx.agent

        invocation = invocation_service.create_record(
            InvocationRecordCreate(
                request_id=ctx.request_id or str(uuid4()),
                agent_id=agent.id,
                org_unit_id=subject.org_unit_id,
                user_id=subject.user_id,
                api_key_id=subject.api_key_id,
                caller_type=CallerType(subject.caller_type),
                source_channel="INTERNAL_API" if subject.api_key_id else "INTERNAL_WEB",
                operation_type=OperationType.CONTRACT_REVIEW,
                input={
                    "contract_review_task_id": task.id,
                    "file_parse_task_id": task.file_parse_task_id,
                    "contract_type": task.contract_type,
                    "counterparty_level": task.counterparty_level,
                },
                stream_mode=False,
            )
        )
        ctx.state["invocation"] = invocation
        task.invocation_record_id = invocation.id
        task.status = ContractReviewTaskStatus.RUNNING
        task.error_message = None
        task.finished_at = None
        ctx.db.add(task)
        ctx.db.commit()
        ctx.db.refresh(task)

    def finalize_success(
        self,
        ctx: TaskContext,
        pre: PreprocessResult,
        core: CoreResult,
        post: PostprocessResult,
        *,
        latency_ms: int,
    ) -> ContractReviewTask:
        """写 SUCCEEDED invocation 与业务任务。"""
        task: ContractReviewTask = ctx.state["task"]
        invocation: AgentInvocationRecord = ctx.state["invocation"]
        invocation_service: InvocationService = ctx.state["invocation_service"]

        invocation_service.finish_record(
            invocation.id,
            InvocationRecordFinish(
                output=post.output_for_invocation or post.business_result,
                status=InvocationStatus.SUCCEEDED,
                token_usage=post.token_usage or {"total_tokens": core.total_tokens},
                latency_ms=latency_ms,
                snapshot=self._build_snapshot(
                    ctx,
                    preprocess_extras=pre.extras,
                    core=core,
                    runtime_extra=post.snapshot_runtime_extra,
                ),
            ),
        )
        task.result = post.business_result
        task.status = ContractReviewTaskStatus.SUCCEEDED
        task.error_message = None
        task.finished_at = datetime.now(timezone.utc)
        return self._save_task(ctx, task)

    def finalize_failure(
        self,
        ctx: TaskContext,
        exc: Exception,
        *,
        latency_ms: int,
    ) -> ContractReviewTask:
        """写 FAILED invocation 与业务任务；主后处理失败不会降级为 warning。"""
        task: ContractReviewTask = ctx.state["task"]
        invocation: AgentInvocationRecord = ctx.state["invocation"]
        invocation_service: InvocationService = ctx.state["invocation_service"]
        core = ctx.state.get("core_result")

        invocation_service.finish_record(
            invocation.id,
            InvocationRecordFinish(
                output={},
                status=InvocationStatus.FAILED,
                error_code=exc.__class__.__name__,
                error_message=str(exc),
                latency_ms=latency_ms,
                snapshot=self._build_snapshot(
                    ctx,
                    preprocess_extras=ctx.state.get("preprocess_extras") or {},
                    core=core,
                    runtime_extra={},
                ),
            ),
        )
        task.status = ContractReviewTaskStatus.FAILED
        task.error_message = str(exc)
        task.finished_at = datetime.now(timezone.utc)
        return self._save_task(ctx, task)

    @staticmethod
    def _assert_contract_review_agent(agent) -> None:
        raw_type = getattr(agent, "type", None)
        agent_type = raw_type.value if isinstance(raw_type, AgentType) else str(raw_type)
        if agent_type != AgentType.CONTRACT_REVIEW.value:
            raise UnsupportedRuntimeError(
                f"agent type must be CONTRACT_REVIEW for this task handler, got: {agent_type}"
            )

    @staticmethod
    def _save_task(ctx: TaskContext, task: ContractReviewTask) -> ContractReviewTask:
        ctx.db.add(task)
        ctx.db.commit()
        ctx.db.refresh(task)
        return task

    @staticmethod
    def _build_snapshot(
        ctx: TaskContext,
        *,
        preprocess_extras: dict,
        core: CoreResult | None,
        runtime_extra: dict,
    ) -> dict:
        task: ContractReviewTask = ctx.state["task"]
        agent = ctx.agent
        runtime_snapshot = {
            **runtime_extra,
            "runtime_type": agent.runtime_type,
            "runtime_app_id": agent.runtime_app_id,
            "inputs": {
                "schema_version": preprocess_extras.get("schema_version"),
                "contract_review_task_id": task.id,
                "file_parse_task_id": task.file_parse_task_id,
                "contract_type": task.contract_type,
                "counterparty_level": task.counterparty_level,
                "context_chars": preprocess_extras.get("context_chars"),
            },
        }
        if core is not None:
            runtime_snapshot.update(
                {
                    "workflow_run_id": core.workflow_run_id,
                    "workflow_status": core.status,
                    "workflow_elapsed_seconds": core.elapsed_time,
                    "workflow_outputs": core.outputs,
                }
            )
        return {
            "retrieval": {},
            "model": {},
            "runtime": runtime_snapshot,
        }

"""任务型 **TaskHandler** 抽象层。

与对话流 ``ChatHandler``（``modules/agent/handlers/``）并列：

- **ChatHandler**：``POST /api/v1/chat/{agent_code}`` SSE 流式对话；
- **TaskHandler**：业务任务状态机 + 可插拔前处理 / 核心处理 / 后处理流水线。

TaskHandlerRegistry 按 ``agent.type`` 工厂分发，每次 ``select`` 创建新实例。
未注册 type 明确报错，不得回退为 ChatHandler / QA。

鉴权由 endpoint 完成（合同审查主路径为 API Key + scope）；TaskHandler 只接收
已鉴权的 ``AuthenticatedSubject``，不自行解析密钥。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any

from sqlalchemy.orm import Session

from app.core.enums import AgentType
from app.core.exceptions import UnsupportedRuntimeError
from app.modules.agent.models import Agent
from app.modules.agent.runtime import AgentRuntimeService
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
from app.modules.auth.schemas import AuthenticatedSubject


@dataclass
class TaskContext:
    """一次任务执行的上下文，由 endpoint / worker 组装后传给 TaskHandler。"""

    db: Session
    subject: AuthenticatedSubject
    task_id: str
    agent: Agent
    runtime_service: AgentRuntimeService
    request_id: str | None = None
    state: dict[str, Any] = field(default_factory=dict)


class TaskHandler(ABC):
    """任务型 handler 模板。

    ``execute`` 是唯一权威编排：执行前校验与状态包装后，严格调用
    ``preprocess -> core -> postprocess``，最后进入成功或失败 finalize。
    具体 Agent 只需声明有序步骤列表并实现持久化钩子；增加步骤不改 endpoint。
    """

    @property
    @abstractmethod
    def preprocess_steps(self) -> Sequence[TaskPreprocessStep]:
        """返回有序前处理步骤。"""

    @property
    @abstractmethod
    def core_step(self) -> TaskCoreStep:
        """返回唯一核心处理步骤。"""

    @property
    @abstractmethod
    def postprocess_steps(self) -> Sequence[TaskPostprocessStep]:
        """返回有序后处理步骤。"""

    def prepare_execution(self, ctx: TaskContext) -> None:
        """在创建 invocation 前执行归属、状态、agent.type 等校验。"""

    def begin_execution(self, ctx: TaskContext) -> None:
        """进入 RUNNING 并创建 invocation；由具体领域实现。"""

    def preprocess(self, ctx: TaskContext) -> PreprocessResult:
        """执行全部前处理步骤。"""
        return run_preprocess_steps(self.preprocess_steps, ctx)

    async def core(self, ctx: TaskContext, pre: PreprocessResult) -> CoreResult:
        """执行核心处理步骤。"""
        return await self.core_step.run(ctx, pre)

    def postprocess(
        self,
        ctx: TaskContext,
        pre: PreprocessResult,
        core: CoreResult,
    ) -> PostprocessResult:
        """执行全部后处理步骤。"""
        return run_postprocess_steps(self.postprocess_steps, ctx, pre, core)

    @abstractmethod
    def finalize_success(
        self,
        ctx: TaskContext,
        pre: PreprocessResult,
        core: CoreResult,
        post: PostprocessResult,
        *,
        latency_ms: int,
    ) -> Any:
        """持久化成功终态并返回领域结果。"""

    @abstractmethod
    def finalize_failure(
        self,
        ctx: TaskContext,
        exc: Exception,
        *,
        latency_ms: int,
    ) -> Any:
        """持久化失败终态并返回领域结果。"""

    async def execute(self, ctx: TaskContext) -> Any:
        """模板执行：状态包装 + preprocess -> core -> postprocess -> finalize。"""
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


TaskHandlerFactory = Callable[[], TaskHandler]


class TaskHandlerRegistry:
    """按 ``agent.type`` 分发 TaskHandler 的注册表（工厂模式）。"""

    def __init__(self, factories: dict[str, TaskHandlerFactory] | None = None):
        if factories is None:
            from app.modules.agent.task_handlers.contract_review import (
                ContractReviewTaskHandler,
            )

            factories = {AgentType.CONTRACT_REVIEW.value: ContractReviewTaskHandler}
        self._factories = factories

    def select(self, agent: Agent) -> TaskHandler:
        """按 agent.type 创建新的 TaskHandler；未注册抛错，不回退 ChatHandler。"""
        raw_type = getattr(agent, "type", None)
        if raw_type is None:
            raise UnsupportedRuntimeError("agent type is required for task handlers")
        agent_type = raw_type.value if isinstance(raw_type, AgentType) else str(raw_type)
        factory = self._factories.get(agent_type)
        if factory is None:
            raise UnsupportedRuntimeError(f"unsupported task agent type: {agent_type}")
        return factory()


_default_registry: TaskHandlerRegistry | None = None


def get_task_handler_registry() -> TaskHandlerRegistry:
    """获取默认 TaskHandler 注册表（惰性初始化）。"""
    global _default_registry
    if _default_registry is None:
        _default_registry = TaskHandlerRegistry()
    return _default_registry

"""任务型 **TaskHandler** 抽象层。

与对话流 ``ChatHandler``（``modules/agent/handlers/``）并列：

- **ChatHandler**：``POST /api/v1/chat/{agent_code}`` SSE 流式对话；
- **TaskHandler**：业务任务状态机 + **可插拔前处理 / 核心处理 / 后处理** 流水线
  （如合同审查 ``CONTRACT_REVIEW``）。

TaskHandlerRegistry 按 ``agent.type`` 工厂分发，每次 ``select`` 创建新实例。
未注册 type 明确报错，不得回退为 ChatHandler / QA。

鉴权由 endpoint 完成（合同审查主路径为 API Key + scope）；TaskHandler 只接收
已鉴权的 ``AuthenticatedSubject``，不自行解析密钥。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from sqlalchemy.orm import Session

from app.core.enums import AgentType
from app.core.exceptions import UnsupportedRuntimeError
from app.modules.agent.models import Agent
from app.modules.agent.runtime import AgentRuntimeService
from app.modules.auth.schemas import AuthenticatedSubject


@dataclass
class TaskContext:
    """一次任务执行的上下文，由 endpoint / 门面组装后传给 TaskHandler。

    Attributes:
        db: SQLAlchemy 会话。
        subject: 已鉴权主体（API Key 场景含 api_key_id 与 scopes）。
        task_id: 业务任务 ID。
        agent: 平台 Agent 配置。
        runtime_service: 平台 runtime 门面；core 阶段只经此调用 workflow。
        request_id: 外部请求 ID。
        state: 阶段间可变状态（仅限当次 handler 实例）。
    """

    db: Session
    subject: AuthenticatedSubject
    task_id: str
    agent: Agent
    runtime_service: AgentRuntimeService
    request_id: str | None = None
    state: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class TaskHandler(Protocol):
    """任务型 handler 协议：驱动 preprocess → core → postprocess 流水线。

    实现类应在 ``execute`` 内完成任务状态与 ``agent_invocation_record`` 的
    写入（任务型 finalize 在 handler，与 chat 的 endpoint finalize 不同）。
    """

    async def execute(self, ctx: TaskContext) -> Any:
        """执行任务流水线并返回领域任务实体或结果。"""
        ...

    async def resume(self, ctx: TaskContext, resume_payload: dict[str, Any]) -> Any:
        """可选恢复入口；未启用的 handler 明确拒绝。"""
        del ctx, resume_payload
        raise UnsupportedRuntimeError("task handler does not support resume")

    def finalize_suspended(self, ctx: TaskContext, suspended: Any) -> Any:
        """可选暂停收口；未启用的 handler 明确拒绝。"""
        del ctx, suspended
        raise UnsupportedRuntimeError("task handler does not support suspension")


TaskHandlerFactory = Callable[[], TaskHandler]


class TaskHandlerRegistry:
    """按 ``agent.type`` 分发 TaskHandler 的注册表（工厂模式）。"""

    def __init__(self, factories: dict[str, TaskHandlerFactory] | None = None):
        if factories is None:
            from app.modules.agent.task_handlers.contract_review import (
                ContractReviewTaskHandler,
            )
            from app.modules.agent.task_handlers.risk_assessment import (
                RiskAssessmentTaskHandler,
            )

            factories = {
                AgentType.CONTRACT_REVIEW.value: ContractReviewTaskHandler,
                AgentType.RISK_ASSISTANT.value: RiskAssessmentTaskHandler,
            }
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

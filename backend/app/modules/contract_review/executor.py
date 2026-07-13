"""合同审查执行兼容门面：唯一实现仍是 TaskHandler 模板流水线。

endpoint 已直接使用 TaskHandlerRegistry。本门面只供现有 worker/脚本复用相同入口，
不包含第二份 execute 实现。
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.enums import AgentType
from app.modules.agent.runtime import AgentRuntimeService
from app.modules.agent.service import AgentService
from app.modules.agent.task_handlers import (
    TaskContext,
    TaskHandlerRegistry,
    get_task_handler_registry,
)
from app.modules.agent.task_handlers.contract_review import ContractReviewTaskHandler
from app.modules.auth.schemas import AuthenticatedSubject
from app.modules.contract_review.models import ContractReviewTask
from app.modules.contract_review.rules import CreditClauseRuleEngine
from app.modules.contract_review.service import ContractReviewService


class ContractReviewExecutionService:
    """为 worker/脚本保留的薄门面，委托 registry 选择并执行 TaskHandler。"""

    def __init__(
        self,
        db: Session,
        *,
        runtime_service: AgentRuntimeService | None = None,
        rule_engine: CreditClauseRuleEngine | None = None,
        registry: TaskHandlerRegistry | None = None,
    ) -> None:
        self.db = db
        self.runtime_service = runtime_service or AgentRuntimeService()
        if registry is not None:
            self.registry = registry
        elif runtime_service is not None or rule_engine is not None:
            self.registry = TaskHandlerRegistry(
                factories={
                    AgentType.CONTRACT_REVIEW.value: lambda: ContractReviewTaskHandler(
                        runtime_service=self.runtime_service,
                        rule_engine=rule_engine,
                    )
                }
            )
        else:
            self.registry = get_task_handler_registry()

    async def execute_task(
        self,
        *,
        task_id: str,
        subject: AuthenticatedSubject,
        request_id: str | None = None,
    ) -> ContractReviewTask:
        """校验归属、加载 Agent，再委托 TaskHandlerRegistry 执行。"""
        task = ContractReviewService(self.db).get_task(task_id=task_id, subject=subject)
        agent = AgentService(self.db).get_agent_by_code(task.agent_code)
        handler = self.registry.select(agent)
        return await handler.execute(
            TaskContext(
                db=self.db,
                subject=subject,
                task_id=task_id,
                agent=agent,
                runtime_service=self.runtime_service,
                request_id=request_id,
            )
        )

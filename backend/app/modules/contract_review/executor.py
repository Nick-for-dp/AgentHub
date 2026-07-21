"""合同审查执行门面：委托 TaskHandler 流水线。

保留模块路径 ``executor`` 以便过渡；唯一执行实现为
``ContractReviewTaskHandler``（preprocess → core → postprocess）。
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
    """兼容门面：加载任务与 Agent 后交给 TaskHandlerRegistry / ContractReviewTaskHandler。"""

    def __init__(
        self,
        db: Session,
        *,
        runtime_service: AgentRuntimeService | None = None,
        rule_engine: CreditClauseRuleEngine | None = None,
        registry: TaskHandlerRegistry | None = None,
    ) -> None:
        self.db = db
        self.agent_service = AgentService(db)
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
        """执行一条待处理合同审查任务（经 TaskHandler 流水线）。"""
        task = ContractReviewService(self.db).get_task(task_id=task_id, subject=subject)
        agent = self.agent_service.get_agent_by_code(task.agent_code)
        handler = self.registry.select(agent)

        ctx = TaskContext(
            db=self.db,
            subject=subject,
            task_id=task_id,
            agent=agent,
            runtime_service=self.runtime_service,
            request_id=request_id,
        )
        return await handler.execute(ctx)

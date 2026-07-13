from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.core.responses import APIResponse, success
from app.db.session import get_db
from app.modules.agent.runtime import AgentRuntimeService
from app.modules.agent.service import AgentService
from app.modules.agent.task_handlers import TaskContext, get_task_handler_registry
from app.modules.auth.dependencies import get_current_subject
from app.modules.auth.schemas import AuthenticatedSubject
from app.modules.contract_review.schemas import (
    ContractReviewTaskCreate,
    ContractReviewTaskRead,
)
from app.modules.contract_review.service import ContractReviewService

router = APIRouter()


@router.post("/tasks", response_model=APIResponse[ContractReviewTaskRead])
def create_contract_review_task(
    payload: ContractReviewTaskCreate,
    subject: AuthenticatedSubject = Depends(get_current_subject),
    db: Session = Depends(get_db),
) -> APIResponse[ContractReviewTaskRead]:
    """创建合同审查任务。

    认证：``get_current_subject``（主路径 API Key）。
    授权：API Key 需 scope ``agent:contract_review:invoke`` 或 ``*``。
    创建只落 PENDING，不触发 runtime / TaskHandler 流水线。
    """
    result = ContractReviewService(db).create_task(payload=payload, subject=subject)
    return success(ContractReviewTaskRead.model_validate(result))


@router.get("/tasks/{task_id}", response_model=APIResponse[ContractReviewTaskRead])
def get_contract_review_task(
    task_id: str,
    subject: AuthenticatedSubject = Depends(get_current_subject),
    db: Session = Depends(get_db),
) -> APIResponse[ContractReviewTaskRead]:
    """查询合同审查任务状态与结果（校验任务归属）。"""
    result = ContractReviewService(db).get_task(task_id=task_id, subject=subject)
    return success(ContractReviewTaskRead.model_validate(result))


@router.post("/tasks/{task_id}/cancel", response_model=APIResponse[ContractReviewTaskRead])
def cancel_contract_review_task(
    task_id: str,
    subject: AuthenticatedSubject = Depends(get_current_subject),
    db: Session = Depends(get_db),
) -> APIResponse[ContractReviewTaskRead]:
    """取消 PENDING 合同审查任务（校验归属）。"""
    result = ContractReviewService(db).cancel_task(task_id=task_id, subject=subject)
    return success(ContractReviewTaskRead.model_validate(result))


@router.post("/tasks/{task_id}/execute", response_model=APIResponse[ContractReviewTaskRead])
async def execute_contract_review_task(
    task_id: str,
    x_request_id: str | None = Header(default=None),
    subject: AuthenticatedSubject = Depends(get_current_subject),
    db: Session = Depends(get_db),
) -> APIResponse[ContractReviewTaskRead]:
    """执行待处理合同审查任务。

    认证：``get_current_subject``（主路径 API Key）。
    编排：按 agent.type 选择 TaskHandler，运行 preprocess → core → postprocess。
    endpoint 保持薄：不 import Dify、不实现规则判敏。
    """
    # 必须先校验任务归属，再加载 Agent/选择 handler；越权请求不会触发 runtime。
    task = ContractReviewService(db).get_task(task_id=task_id, subject=subject)
    agent = AgentService(db).get_agent_by_code(task.agent_code)
    handler = get_task_handler_registry().select(agent)
    ctx = TaskContext(
        db=db,
        subject=subject,
        task_id=task_id,
        agent=agent,
        runtime_service=AgentRuntimeService(),
        request_id=x_request_id,
    )
    result = await handler.execute(ctx)
    return success(ContractReviewTaskRead.model_validate(result))

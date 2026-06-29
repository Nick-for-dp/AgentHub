from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.responses import APIResponse, success
from app.db.session import get_db
from app.modules.auth.dependencies import get_current_subject
from app.modules.auth.schemas import AuthenticatedSubject
from app.modules.contract_review.handlers import ContractReviewHandler
from app.modules.contract_review.schemas import (
    ContractReviewTaskCreate,
    ContractReviewTaskRead,
)

router = APIRouter()


@router.post("/tasks", response_model=APIResponse[ContractReviewTaskRead])
def create_contract_review_task(
    payload: ContractReviewTaskCreate,
    subject: AuthenticatedSubject = Depends(get_current_subject),
    db: Session = Depends(get_db),
) -> APIResponse[ContractReviewTaskRead]:
    """创建合同审查任务。

    当前阶段要求请求引用一个已成功的 ``file_parse_task.id``，并创建待执行的
    合同审查业务任务。Dify workflow 与规则引擎在后续 worker 阶段接入。
    """
    result = ContractReviewHandler(db).create_task(payload=payload, subject=subject)
    return success(ContractReviewTaskRead.model_validate(result))


@router.get("/tasks/{task_id}", response_model=APIResponse[ContractReviewTaskRead])
def get_contract_review_task(
    task_id: str,
    subject: AuthenticatedSubject = Depends(get_current_subject),
    db: Session = Depends(get_db),
) -> APIResponse[ContractReviewTaskRead]:
    """查询合同审查任务状态与结果。

    MVP 阶段返回 ``contract_review_task`` 的业务状态。真正运行 Agent 后，
    ``invocation_record_id`` 会用于追溯 Dify/LLM 调用记录。
    """
    result = ContractReviewHandler(db).get_task(task_id=task_id, subject=subject)
    return success(ContractReviewTaskRead.model_validate(result))


@router.post("/tasks/{task_id}/cancel", response_model=APIResponse[ContractReviewTaskRead])
def cancel_contract_review_task(
    task_id: str,
    subject: AuthenticatedSubject = Depends(get_current_subject),
    db: Session = Depends(get_db),
) -> APIResponse[ContractReviewTaskRead]:
    """取消合同审查任务。

    当前仅允许取消尚未进入 worker 的 ``PENDING`` 任务；已进入最终态的任务不会被
    重复取消。
    """
    result = ContractReviewHandler(db).cancel_task(task_id=task_id, subject=subject)
    return success(ContractReviewTaskRead.model_validate(result))

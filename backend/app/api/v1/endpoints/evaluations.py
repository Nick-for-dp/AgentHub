from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.responses import APIResponse, success
from app.db.session import get_db
from app.modules.evaluation.schemas import (
    EvaluationCaseCreate,
    EvaluationCaseRead,
    EvaluationResultCreate,
    EvaluationResultRead,
)
from app.modules.evaluation.service import EvaluationService

router = APIRouter()


@router.get("/cases", response_model=APIResponse[list[EvaluationCaseRead]])
def list_evaluation_cases(db: Session = Depends(get_db)) -> APIResponse[list[EvaluationCaseRead]]:
    items = [EvaluationCaseRead.model_validate(item) for item in EvaluationService(db).list_cases()]
    return success(items)


@router.post("/cases", response_model=APIResponse[EvaluationCaseRead])
def create_evaluation_case(
    payload: EvaluationCaseCreate,
    db: Session = Depends(get_db),
) -> APIResponse[EvaluationCaseRead]:
    case = EvaluationService(db).create_case(payload)
    return success(EvaluationCaseRead.model_validate(case))


@router.get("/results", response_model=APIResponse[list[EvaluationResultRead]])
def list_evaluation_results(
    db: Session = Depends(get_db),
) -> APIResponse[list[EvaluationResultRead]]:
    items = [
        EvaluationResultRead.model_validate(item)
        for item in EvaluationService(db).list_results()
    ]
    return success(items)


@router.post("/results", response_model=APIResponse[EvaluationResultRead])
def create_evaluation_result(
    payload: EvaluationResultCreate,
    db: Session = Depends(get_db),
) -> APIResponse[EvaluationResultRead]:
    result = EvaluationService(db).create_result(payload)
    return success(EvaluationResultRead.model_validate(result))

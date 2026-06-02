from sqlalchemy.orm import Session

from app.modules.evaluation.models import EvaluationCase, EvaluationResult
from app.modules.evaluation.repository import EvaluationRepository
from app.modules.evaluation.schemas import EvaluationCaseCreate, EvaluationResultCreate


class EvaluationService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = EvaluationRepository(db)

    def create_case(self, payload: EvaluationCaseCreate) -> EvaluationCase:
        case = EvaluationCase(**payload.model_dump())
        self.repository.add_case(case)
        self.db.commit()
        self.db.refresh(case)
        return case

    def create_result(self, payload: EvaluationResultCreate) -> EvaluationResult:
        result = EvaluationResult(**payload.model_dump())
        self.repository.add_result(result)
        self.db.commit()
        self.db.refresh(result)
        return result

    def list_cases(self) -> list[EvaluationCase]:
        return self.repository.list_cases()

    def list_results(self) -> list[EvaluationResult]:
        return self.repository.list_results()

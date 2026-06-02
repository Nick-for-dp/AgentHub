from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.evaluation.models import EvaluationCase, EvaluationResult


class EvaluationRepository:
    def __init__(self, db: Session):
        self.db = db

    def add_case(self, case: EvaluationCase) -> EvaluationCase:
        self.db.add(case)
        self.db.flush()
        return case

    def add_result(self, result: EvaluationResult) -> EvaluationResult:
        self.db.add(result)
        self.db.flush()
        return result

    def list_cases(self, limit: int = 100, offset: int = 0) -> list[EvaluationCase]:
        stmt = select(EvaluationCase).order_by(EvaluationCase.created_at.desc()).limit(limit).offset(offset)
        return list(self.db.scalars(stmt))

    def list_results(self, limit: int = 100, offset: int = 0) -> list[EvaluationResult]:
        stmt = select(EvaluationResult).order_by(EvaluationResult.created_at.desc()).limit(limit).offset(offset)
        return list(self.db.scalars(stmt))

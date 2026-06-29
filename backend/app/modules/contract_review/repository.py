from sqlalchemy.orm import Session

from app.modules.contract_review.models import ContractReviewTask


class ContractReviewTaskRepository:
    """合同审查任务数据访问层。"""

    def __init__(self, db: Session):
        """初始化仓储实例。"""
        self.db = db

    def add_task(self, task: ContractReviewTask) -> None:
        """添加合同审查任务到当前 session。"""
        self.db.add(task)

    def get_task(self, task_id: str) -> ContractReviewTask | None:
        """按 ID 查询合同审查任务。"""
        return self.db.get(ContractReviewTask, task_id)

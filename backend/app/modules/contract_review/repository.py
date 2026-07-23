from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.contract_review.models import ContractReviewTask
from app.modules.file_parse.models import FileParseTask


class ContractReviewTaskRepository:
    """合同审查任务数据访问层。"""

    def __init__(self, db: Session):
        """初始化仓储实例。"""
        self.db = db

    def add_task(self, task: ContractReviewTask) -> None:
        """添加合同审查任务到当前 session。"""
        self.db.add(task)

    def get_task(
        self,
        task_id: str,
        *,
        for_update: bool = False,
        include_deleted: bool = False,
    ) -> ContractReviewTask | None:
        """按 ID 查询合同审查任务；业务查询默认排除已逻辑删除记录。"""
        statement = select(ContractReviewTask).where(ContractReviewTask.id == task_id)
        if not include_deleted:
            statement = statement.where(ContractReviewTask.deleted_at.is_(None))
        if for_update:
            statement = statement.with_for_update()
        return self.db.scalar(statement)

    def list_tasks(
        self,
        *,
        created_by: str | None = None,
        api_key_id: str | None = None,
        owner_org_unit_id: str | None = None,
        status: str | None = None,
        contract_type: str | None = None,
        keyword: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[tuple[ContractReviewTask, str | None]], int]:
        """分页查询当前主体可见的未删除合同审查记录。"""
        filters = [ContractReviewTask.deleted_at.is_(None)]
        if api_key_id:
            filters.append(ContractReviewTask.api_key_id == api_key_id)
        elif created_by:
            filters.append(ContractReviewTask.created_by == created_by)
        elif owner_org_unit_id:
            filters.append(ContractReviewTask.owner_org_unit_id == owner_org_unit_id)
        else:
            return [], 0

        if status is not None:
            filters.append(ContractReviewTask.status == status)
        if contract_type is not None:
            filters.append(ContractReviewTask.contract_type == contract_type)
        if keyword:
            filters.append(FileParseTask.original_filename.contains(keyword, autoescape=True))

        from_clause = ContractReviewTask.__table__.join(
            FileParseTask.__table__,
            FileParseTask.id == ContractReviewTask.file_parse_task_id,
        )
        total = int(
            self.db.scalar(
                select(func.count())
                .select_from(from_clause)
                .where(*filters)
            )
            or 0
        )
        statement = (
            select(ContractReviewTask, FileParseTask.original_filename)
            .join(FileParseTask, FileParseTask.id == ContractReviewTask.file_parse_task_id)
            .where(*filters)
            .order_by(
                ContractReviewTask.created_at.desc(),
                ContractReviewTask.id.desc(),
            )
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
        return [(row[0], row[1]) for row in self.db.execute(statement)], total

"""合同审查任务应用服务（CRUD、scope 与归属）。

真正的执行由 ``ContractReviewTaskHandler`` 模板流水线完成。本服务保留既有
API Key scope ``agent:contract_review:invoke``（或 ``*``）以及 api_key/user/org
归属语义，供 create、endpoint 和 TaskHandler 前处理复用。
"""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.enums import ContractReviewTaskStatus, FileParseTaskStatus
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.modules.auth.schemas import AuthenticatedSubject
from app.modules.contract_review.models import ContractReviewTask
from app.modules.contract_review.repository import ContractReviewTaskRepository
from app.modules.contract_review.schemas import ContractReviewTaskCreate
from app.modules.file_parse.models import FileParseTask

CONTRACT_REVIEW_INVOKE_SCOPE = "agent:contract_review:invoke"


def assert_contract_review_scope(subject: AuthenticatedSubject) -> None:
    """API Key 调用必须包含合同审查 invoke scope 或通配 scope。"""
    if subject.api_key_id is None:
        return
    if "*" in subject.scopes or CONTRACT_REVIEW_INVOKE_SCOPE in subject.scopes:
        return
    raise ForbiddenError("api key scope does not allow contract review invocation")


def is_subject_owner(task, subject: AuthenticatedSubject) -> bool:
    """按既有 api_key -> user -> org 优先级判断资源归属。"""
    if task.api_key_id and subject.api_key_id:
        return task.api_key_id == subject.api_key_id
    if task.created_by and subject.user_id:
        return task.created_by == subject.user_id
    if task.owner_org_unit_id and subject.org_unit_id:
        return task.owner_org_unit_id == subject.org_unit_id
    return False


class ContractReviewService:
    """合同审查任务 CRUD 应用服务（非 TaskHandler / 非 ChatHandler）。"""

    def __init__(self, db: Session):
        self.db = db
        self.repository = ContractReviewTaskRepository(db)

    def create_task(
        self,
        *,
        payload: ContractReviewTaskCreate,
        subject: AuthenticatedSubject,
    ) -> ContractReviewTask:
        """创建 PENDING 任务，不触发 runtime 或 invocation。"""
        assert_contract_review_scope(subject)
        file_parse_task = self.get_owned_file_parse_task(payload.file_parse_task_id, subject)
        if file_parse_task.status != FileParseTaskStatus.SUCCEEDED:
            raise ConflictError("file parse task must be succeeded before contract review")
        task = ContractReviewTask(
            owner_org_unit_id=subject.org_unit_id,
            created_by=subject.user_id,
            api_key_id=subject.api_key_id,
            agent_code=payload.agent_code,
            file_parse_task_id=file_parse_task.id,
            contract_type=payload.contract_type,
            counterparty_level=payload.counterparty_level.value,
            rule_set_version=payload.rule_set_version,
            callback_metadata=payload.callback_metadata,
            status=ContractReviewTaskStatus.PENDING,
        )
        self.repository.add_task(task)
        self.db.commit()
        self.db.refresh(task)
        return task

    def get_task(
        self,
        *,
        task_id: str,
        subject: AuthenticatedSubject,
    ) -> ContractReviewTask:
        """查询合同审查任务并校验归属。"""
        task = self.repository.get_task(task_id)
        if task is None:
            raise NotFoundError("contract review task not found")
        if not is_subject_owner(task, subject):
            raise ForbiddenError("permission denied")
        return task

    def cancel_task(
        self,
        *,
        task_id: str,
        subject: AuthenticatedSubject,
    ) -> ContractReviewTask:
        """取消待执行合同审查任务（仅 PENDING）。"""
        task = self.get_task(task_id=task_id, subject=subject)
        if task.status != ContractReviewTaskStatus.PENDING:
            raise ConflictError("only pending contract review task can be cancelled")
        task.status = ContractReviewTaskStatus.CANCELLED
        task.finished_at = datetime.now(timezone.utc)
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return task

    def get_owned_file_parse_task(
        self,
        file_parse_task_id: str,
        subject: AuthenticatedSubject,
    ) -> FileParseTask:
        """读取并校验解析任务归属。"""
        task = self.db.get(FileParseTask, file_parse_task_id)
        if task is None:
            raise NotFoundError("file parse task not found")
        if not is_subject_owner(task, subject):
            raise ForbiddenError("permission denied")
        return task

    def get_ready_file_parse_task(
        self,
        file_parse_task_id: str,
        subject: AuthenticatedSubject,
    ) -> FileParseTask:
        """读取执行上下文所需的已成功解析任务。"""
        task = self.get_owned_file_parse_task(file_parse_task_id, subject)
        if task.status != FileParseTaskStatus.SUCCEEDED:
            raise ConflictError("file parse task must be succeeded before contract review")
        return task

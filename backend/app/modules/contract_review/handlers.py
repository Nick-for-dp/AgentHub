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


class ContractReviewHandler:
    """合同审查 Agent MVP handler。

    当前阶段负责创建、查询和取消合同审查业务任务，并把任务与
    ``file_parse_task.id`` 关联起来。Dify workflow 与规则引擎尚未接入，因此创建后
    任务保持 ``PENDING``；后续真正触发 runtime 时才写 ``agent_invocation_record``。
    """

    def __init__(self, db: Session):
        """初始化合同审查 handler。"""
        self.db = db
        self.repository = ContractReviewTaskRepository(db)

    def create_task(
        self,
        *,
        payload: ContractReviewTaskCreate,
        subject: AuthenticatedSubject,
    ) -> ContractReviewTask:
        """创建合同审查任务。

        Args:
            payload: 合同审查任务创建请求。
            subject: 已认证主体，API Key 必须包含 ``agent:contract_review:invoke``。

        Returns:
            ContractReviewTask: 新建的待执行合同审查任务。

        Raises:
            ForbiddenError: 缺 scope 或引用了不属于当前主体的解析任务。
            ConflictError: 解析任务尚未成功，不能进入合同审查。
        """
        self._assert_contract_review_scope(subject)
        file_parse_task = self._get_owned_file_parse_task(payload.file_parse_task_id, subject)
        if file_parse_task.status != FileParseTaskStatus.SUCCEEDED:
            raise ConflictError("file parse task must be succeeded before contract review")
        task = ContractReviewTask(
            owner_org_unit_id=subject.org_unit_id,
            created_by=subject.user_id,
            api_key_id=subject.api_key_id,
            agent_code=payload.agent_code,
            file_parse_task_id=file_parse_task.id,
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
        task = self._get_owned_task(task_id, subject)
        return task

    def cancel_task(
        self,
        *,
        task_id: str,
        subject: AuthenticatedSubject,
    ) -> ContractReviewTask:
        """取消待执行合同审查任务。

        MVP 阶段仅允许取消 ``PENDING`` 任务。未来接入 worker 后，可扩展 RUNNING 的
        协作取消语义。
        """
        task = self._get_owned_task(task_id, subject)
        if task.status != ContractReviewTaskStatus.PENDING:
            raise ConflictError("only pending contract review task can be cancelled")
        task.status = ContractReviewTaskStatus.CANCELLED
        task.finished_at = datetime.now(timezone.utc)
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return task

    @staticmethod
    def _assert_contract_review_scope(subject: AuthenticatedSubject) -> None:
        """校验合同审查 API Key scope。"""
        if subject.api_key_id is None:
            return
        if "*" in subject.scopes or CONTRACT_REVIEW_INVOKE_SCOPE in subject.scopes:
            return
        raise ForbiddenError("api key scope does not allow contract review invocation")

    def _get_owned_file_parse_task(
        self,
        file_parse_task_id: str,
        subject: AuthenticatedSubject,
    ) -> FileParseTask:
        """读取并校验解析任务归属。"""
        task = self.db.get(FileParseTask, file_parse_task_id)
        if task is None:
            raise NotFoundError("file parse task not found")
        if not self._is_subject_owner(task, subject):
            raise ForbiddenError("permission denied")
        return task

    def _get_owned_task(self, task_id: str, subject: AuthenticatedSubject) -> ContractReviewTask:
        """读取并校验合同审查任务归属。"""
        task = self.repository.get_task(task_id)
        if task is None:
            raise NotFoundError("contract review task not found")
        if not self._is_subject_owner(task, subject):
            raise ForbiddenError("permission denied")
        return task

    @staticmethod
    def _is_subject_owner(task, subject: AuthenticatedSubject) -> bool:
        """判断任务是否归属于当前认证主体。"""
        if task.api_key_id and subject.api_key_id:
            return task.api_key_id == subject.api_key_id
        if task.created_by and subject.user_id:
            return task.created_by == subject.user_id
        if task.owner_org_unit_id and subject.org_unit_id:
            return task.owner_org_unit_id == subject.org_unit_id
        return False

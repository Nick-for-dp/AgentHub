"""合同审查任务应用服务（CRUD）。

负责创建、查询、取消合同审查业务任务，并强制 **API Key scope** 与任务归属校验。
真正的执行走 ``TaskHandler`` 流水线（``modules/agent/task_handlers``），不在本类实现。

鉴权模型（保持不变）：
- endpoint 经 ``get_current_subject`` 认证；
- 主调用方为 API Key；create 要求 scope ``agent:contract_review:invoke`` 或 ``*``；
- 任务记录 ``api_key_id``，查询/取消/执行校验归属。
"""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.enums import ContractReviewTaskStatus, FileParseTaskStatus
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.modules.auth.schemas import AuthenticatedSubject
from app.modules.contract_review.models import ContractReviewTask
from app.modules.contract_review.repository import ContractReviewTaskRepository
from app.modules.contract_review.schemas import (
    ContractReviewTaskCreate,
    ContractReviewTaskPageRead,
    ContractReviewTaskSummaryRead,
)
from app.modules.file_parse.models import FileParseTask

CONTRACT_REVIEW_INVOKE_SCOPE = "agent:contract_review:invoke"

# 兼容旧 import 名（测试/脚本过渡期）
ContractReviewHandler = None  # 在文件末尾赋值为 ContractReviewService


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
        """创建合同审查任务（仅 PENDING，不触发 runtime）。

        API Key 必须包含 ``agent:contract_review:invoke`` 或 ``*``。
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
        return self._get_owned_task(task_id, subject)

    def list_tasks(
        self,
        *,
        subject: AuthenticatedSubject,
        page: int = 1,
        page_size: int = 20,
        status: ContractReviewTaskStatus | None = None,
        contract_type: str | None = None,
        keyword: str | None = None,
    ) -> ContractReviewTaskPageRead:
        """按当前主体分页查询未删除的合同审查工作记录。"""
        owner = self._subject_owner_filter(subject)
        rows, total = self.repository.list_tasks(
            **owner,
            status=status.value if status is not None else None,
            contract_type=contract_type,
            keyword=keyword.strip() if keyword and keyword.strip() else None,
            page=page,
            page_size=page_size,
        )
        return ContractReviewTaskPageRead(
            items=[self._to_task_summary(task, filename) for task, filename in rows],
            total=total,
            page=page,
            page_size=page_size,
        )

    def cancel_task(
        self,
        *,
        task_id: str,
        subject: AuthenticatedSubject,
    ) -> ContractReviewTask:
        """取消待执行合同审查任务（仅 PENDING）。"""
        task = self._get_owned_task(task_id, subject)
        if task.status != ContractReviewTaskStatus.PENDING:
            raise ConflictError("only pending contract review task can be cancelled")
        task.status = ContractReviewTaskStatus.CANCELLED
        task.finished_at = datetime.now(timezone.utc)
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return task

    def delete_task(
        self,
        *,
        task_id: str,
        subject: AuthenticatedSubject,
    ) -> ContractReviewTask:
        """逻辑删除已结束的合同审查工作记录，保留文件与调用审计数据。"""
        if subject.api_key_id or subject.caller_type.upper() != "USER" or not subject.user_id:
            raise ForbiddenError("contract review work record deletion requires internal user")
        task = self._get_owned_task(task_id, subject, for_update=True)
        if task.status not in {
            ContractReviewTaskStatus.SUCCEEDED,
            ContractReviewTaskStatus.FAILED,
            ContractReviewTaskStatus.CANCELLED,
        }:
            raise ConflictError("only terminal contract review task can be deleted")
        task.deleted_at = datetime.now(timezone.utc)
        task.deleted_by_user_id = subject.user_id
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
        task = self.db.get(FileParseTask, file_parse_task_id)
        if task is None:
            raise NotFoundError("file parse task not found")
        if not self._is_subject_owner(task, subject):
            raise ForbiddenError("permission denied")
        return task

    def get_owned_file_parse_task(
        self,
        file_parse_task_id: str,
        subject: AuthenticatedSubject,
    ) -> FileParseTask:
        """兼容旧公共入口：读取并校验解析任务归属。"""
        return self._get_owned_file_parse_task(file_parse_task_id, subject)

    def get_ready_file_parse_task(
        self,
        file_parse_task_id: str,
        subject: AuthenticatedSubject,
    ) -> FileParseTask:
        """读取执行上下文所需的已成功解析任务。"""
        task = self._get_owned_file_parse_task(file_parse_task_id, subject)
        if task.status != FileParseTaskStatus.SUCCEEDED:
            raise ConflictError("file parse task must be succeeded before contract review")
        return task

    def _get_owned_task(
        self,
        task_id: str,
        subject: AuthenticatedSubject,
        *,
        for_update: bool = False,
    ) -> ContractReviewTask:
        task = self.repository.get_task(task_id, for_update=for_update)
        if task is None:
            raise NotFoundError("contract review task not found")
        if not self._is_subject_owner(task, subject):
            raise ForbiddenError("permission denied")
        return task

    @staticmethod
    def _subject_owner_filter(subject: AuthenticatedSubject) -> dict[str, str | None]:
        """按与单任务归属校验相同的优先级生成列表查询条件。"""
        if subject.api_key_id:
            return {"api_key_id": subject.api_key_id}
        if subject.user_id:
            return {"created_by": subject.user_id}
        if subject.org_unit_id:
            return {"owner_org_unit_id": subject.org_unit_id}
        return {}

    @staticmethod
    def _to_task_summary(
        task: ContractReviewTask,
        original_filename: str | None,
    ) -> ContractReviewTaskSummaryRead:
        result = task.result if isinstance(task.result, dict) else {}
        summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
        return ContractReviewTaskSummaryRead(
            id=task.id,
            original_filename=original_filename,
            status=task.status,
            contract_type=task.contract_type,
            counterparty_level=task.counterparty_level,
            total_clause_count=_safe_count(summary.get("total_clause_count")),
            sensitive_clause_count=_safe_count(summary.get("sensitive_clause_count")),
            error_message=task.error_message,
            created_at=task.created_at,
            updated_at=task.updated_at,
            finished_at=task.finished_at,
        )

    @staticmethod
    def _is_subject_owner(task, subject: AuthenticatedSubject) -> bool:
        if task.api_key_id and subject.api_key_id:
            return task.api_key_id == subject.api_key_id
        if task.created_by and subject.user_id:
            return task.created_by == subject.user_id
        if task.owner_org_unit_id and subject.org_unit_id:
            return task.owner_org_unit_id == subject.org_unit_id
        return False


def assert_contract_review_scope(subject: AuthenticatedSubject) -> None:
    """兼容旧模块级入口：校验合同审查 API Key scope。"""
    ContractReviewService._assert_contract_review_scope(subject)


def is_subject_owner(task, subject: AuthenticatedSubject) -> bool:
    """兼容旧模块级入口：按既有优先级判断资源归属。"""
    return ContractReviewService._is_subject_owner(task, subject)


# 兼容旧名称，避免测试与脚本瞬间全红
ContractReviewHandler = ContractReviewService


def _safe_count(value: object) -> int:
    """将历史结果中的计数字段安全收敛为非负整数。"""
    if isinstance(value, bool):
        return 0
    try:
        return max(0, int(value))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0

import os
import tempfile
from datetime import datetime, timezone
from pathlib import PurePosixPath, PureWindowsPath
from typing import Awaitable, Callable

from sqlalchemy.orm import Session

from app.core.enums import FileParseTaskStatus
from app.core.exceptions import BadRequestError, ConflictError, ForbiddenError, NotFoundError
from app.integrations.object_storage import FileStorage, create_file_storage, parse_storage_uri
from app.integrations.file_reader.factory import parse_local_file
from app.modules.auth.schemas import AuthenticatedSubject
from app.modules.file_parse.models import FileParseTask
from app.modules.file_parse.repository import FileParseTaskRepository
from app.modules.file_parse.schemas import FileParseTaskCreate

FILE_PARSE_CREATE_SCOPE = "file:parse:create"
FILE_PARSE_READ_SCOPE = "file:parse:read"
SUPPORTED_PARSE_FILE_TYPES = frozenset({"docx", "pdf", "png", "jpg", "jpeg"})


class FileParseService:
    """文件解析任务服务。

    MVP 阶段保持任务 API 形态，但创建任务后同步执行解析，便于先走通
    ``storage_uri -> ParsedDocumentV1`` 闭环。后续接入 arq worker 时，可把
    ``_run_parse_task`` 移到 worker 中，API 契约不需要变化。
    """

    def __init__(
        self,
        db: Session,
        *,
        storage: FileStorage | None = None,
        parser: Callable[[str], Awaitable] = parse_local_file,
    ) -> None:
        self.db = db
        self.repository = FileParseTaskRepository(db)
        self.storage = storage or create_file_storage()
        self.parser = parser

    async def create_task(
        self,
        *,
        payload: FileParseTaskCreate,
        subject: AuthenticatedSubject,
    ) -> FileParseTask:
        """创建并同步执行解析任务。

        Args:
            payload: 解析任务创建请求。
            subject: 已认证主体。API Key 必须具备 ``file:parse:create``。

        Returns:
            FileParseTask: 已进入最终态或失败态的解析任务。
        """
        self._assert_scope(subject, FILE_PARSE_CREATE_SCOPE, "create file parse task")
        bucket, object_key = parse_storage_uri(payload.source_uri)
        file_type = self._extract_supported_file_type(object_key)
        original_filename = self._normalize_original_filename(
            payload.original_filename,
            expected_file_type=file_type,
        )
        task = FileParseTask(
            owner_org_unit_id=subject.org_unit_id,
            created_by=subject.user_id,
            api_key_id=subject.api_key_id,
            source_uri=payload.source_uri,
            original_filename=original_filename,
            file_type=file_type,
            status=FileParseTaskStatus.PENDING,
        )
        self.repository.add_task(task)
        self.db.commit()
        self.db.refresh(task)
        await self._run_parse_task(task.id, bucket=bucket, object_key=object_key)
        refreshed = self.repository.get_task(task.id)
        if refreshed is None:
            raise NotFoundError("file parse task not found")
        return refreshed

    def get_task(self, *, task_id: str, subject: AuthenticatedSubject) -> FileParseTask:
        """查询解析任务。

        API Key 必须具备 ``file:parse:read``；同时调用主体只能读取自己组织/用户/API Key
        创建的任务。
        """
        self._assert_scope(subject, FILE_PARSE_READ_SCOPE, "read file parse task")
        task = self._get_owned_task(task_id, subject)
        return task

    def cancel_task(self, *, task_id: str, subject: AuthenticatedSubject) -> FileParseTask:
        """取消解析任务。

        同步执行 MVP 中通常无法取消 RUNNING 任务；首期只允许取消仍处于 PENDING 的任务。
        """
        self._assert_scope(subject, FILE_PARSE_CREATE_SCOPE, "cancel file parse task")
        task = self._get_owned_task(task_id, subject)
        if task.status != FileParseTaskStatus.PENDING:
            raise ConflictError("only pending file parse task can be cancelled")
        task.status = FileParseTaskStatus.CANCELLED
        task.finished_at = datetime.now(timezone.utc)
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return task

    async def _run_parse_task(
        self,
        task_id: str,
        *,
        bucket: str | None = None,
        object_key: str | None = None,
    ) -> None:
        """执行解析任务。

        从 MinIO 读取对象内容，写入随机临时文件，再调用当前 file_reader 的
        ``parse_local_file``。临时文件只为兼容现有 reader API，finally 中强制删除。
        """
        task = self.repository.get_task(task_id)
        if task is None:
            raise NotFoundError("file parse task not found")
        if task.status == FileParseTaskStatus.CANCELLED:
            return
        if bucket is None or object_key is None:
            bucket, object_key = parse_storage_uri(task.source_uri)

        task.status = FileParseTaskStatus.RUNNING
        task.error_message = None
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)

        temp_path: str | None = None
        try:
            content = self.storage.download_bytes(bucket=bucket, object_key=object_key)
            temp_path = self._write_temp_file(content, task.file_type)
            parsed_document = await self.parser(temp_path)
            parsed_document.metadata.filename = task.original_filename or parsed_document.metadata.filename
            task.reader_type = parsed_document.metadata.reader_type
            task.result_snapshot = parsed_document.to_dict()
            task.status = FileParseTaskStatus.SUCCEEDED
            task.finished_at = datetime.now(timezone.utc)
        except Exception as exc:
            task.status = FileParseTaskStatus.FAILED
            task.error_message = str(exc)
            task.finished_at = datetime.now(timezone.utc)
        finally:
            if temp_path:
                self._remove_temp_file(temp_path)

        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)

    def _get_owned_task(self, task_id: str, subject: AuthenticatedSubject) -> FileParseTask:
        """读取任务并校验归属。"""
        task = self.repository.get_task(task_id)
        if task is None:
            raise NotFoundError("file parse task not found")
        if not self._is_subject_owner(task, subject):
            raise ForbiddenError("permission denied")
        return task

    @staticmethod
    def _assert_scope(subject: AuthenticatedSubject, scope: str, action_name: str) -> None:
        """校验 API Key scope。

        Cookie 用户路径用于内部 Web 工作台；系统间调用必须通过 API Key scope 显式授权。
        """
        if subject.api_key_id is None:
            return
        if "*" in subject.scopes or scope in subject.scopes:
            return
        raise ForbiddenError(f"api key scope does not allow {action_name}")

    @staticmethod
    def _is_subject_owner(task: FileParseTask, subject: AuthenticatedSubject) -> bool:
        if task.api_key_id and subject.api_key_id:
            return task.api_key_id == subject.api_key_id
        if task.created_by and subject.user_id:
            return task.created_by == subject.user_id
        if task.owner_org_unit_id and subject.org_unit_id:
            return task.owner_org_unit_id == subject.org_unit_id
        return False

    @staticmethod
    def _extract_supported_file_type(object_key: str) -> str:
        suffix = PurePosixPath(object_key).suffix.lower().lstrip(".")
        if suffix not in SUPPORTED_PARSE_FILE_TYPES:
            raise BadRequestError(
                "unsupported parse file type; supported types: docx, pdf, png, jpg, jpeg"
            )
        return suffix

    @staticmethod
    def _normalize_original_filename(value: str, *, expected_file_type: str) -> str:
        """只保留客户端文件 basename，并校验扩展名与存储对象一致。"""
        normalized = value.strip().replace("\x00", "")
        filename = PureWindowsPath(normalized).name.strip()
        if not filename or filename in {".", ".."}:
            raise BadRequestError("original filename is required")
        if len(filename) > 255:
            raise BadRequestError("original filename is too long")
        suffix = PureWindowsPath(filename).suffix.lower().lstrip(".")
        if suffix != expected_file_type:
            raise BadRequestError("original filename type does not match source object type")
        return filename

    @staticmethod
    def _write_temp_file(content: bytes, file_type: str) -> str:
        """写入随机临时文件并返回路径。

        Windows 下 NamedTemporaryFile 默认打开后不能被其它库重新打开，因此这里使用
        ``delete=False`` 并在解析完成后手动删除。
        """
        with tempfile.NamedTemporaryFile(
            prefix="agenthub-parse-",
            suffix=f".{file_type}",
            delete=False,
        ) as temp_file:
            temp_file.write(content)
            return temp_file.name

    @staticmethod
    def _remove_temp_file(path: str) -> None:
        """删除解析临时文件。"""
        try:
            os.remove(path)
        except FileNotFoundError:
            return

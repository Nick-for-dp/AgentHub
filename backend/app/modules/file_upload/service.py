import mimetypes
import re
from datetime import datetime, timezone
from pathlib import PureWindowsPath

from uuid6 import uuid7

from app.core.config import Settings, get_settings
from app.core.exceptions import BadRequestError, ForbiddenError
from app.integrations.object_storage import FileStorage, create_file_storage, parse_storage_uri
from app.modules.auth.schemas import AuthenticatedSubject
from app.modules.file_upload.schemas import FileUploadPrepareRequest, FileUploadPrepareResponse

FILE_UPLOAD_SCOPE = "file:upload"
SUPPORTED_UPLOAD_EXTENSIONS = frozenset({".pdf", ".doc", ".docx", ".png", ".jpg", ".jpeg"})
DEFAULT_CONTENT_TYPE = "application/octet-stream"
_SAFE_OWNER_RE = re.compile(r"[^a-zA-Z0-9._-]+")


class FileUploadService:
    """内部文件上传服务。

    负责生成对象存储预签名上传 URL，不直接接收文件正文。上传完成后，调用方应使用
    返回的 ``storage_uri`` 创建解析任务。上传本身不是 Agent 调用，因此本服务不写
    ``agent_invocation_record``。
    """

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        storage: FileStorage | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.storage = storage or create_file_storage(self.settings)

    def prepare_upload(
        self,
        *,
        payload: FileUploadPrepareRequest,
        subject: AuthenticatedSubject,
    ) -> FileUploadPrepareResponse:
        """生成内部文件预签名上传 URL。

        Args:
            payload: 上传文件的基础信息。
            subject: 已认证主体。API Key 调用必须具备 ``file:upload`` scope。

        Returns:
            FileUploadPrepareResponse: 上传 URL、必要 headers 和对象存储 URI。

        Raises:
            ForbiddenError: API Key 缺少 ``file:upload`` scope。
            BadRequestError: 文件扩展名不在首期支持范围内。
        """
        self._assert_upload_scope(subject)
        file_type = self._extract_supported_file_type(payload.filename)
        content_type = self._resolve_content_type(payload.filename, payload.content_type)
        object_key = self._build_object_key(subject=subject, file_type=file_type)
        presigned = self.storage.create_presigned_upload_url(
            bucket=self.settings.object_storage_bucket_raw,
            object_key=object_key,
            content_type=content_type,
            expires_seconds=self.settings.object_storage_presign_expires_seconds,
        )
        bucket, parsed_object_key = parse_storage_uri(presigned.storage_uri)
        return FileUploadPrepareResponse(
            upload_url=presigned.url,
            method=presigned.method,
            headers=presigned.headers,
            storage_uri=presigned.storage_uri,
            bucket=bucket,
            object_key=parsed_object_key,
            original_filename=payload.filename,
            file_type=file_type,
            content_type=content_type,
            expires_seconds=presigned.expires_seconds,
        )

    @staticmethod
    def _assert_upload_scope(subject: AuthenticatedSubject) -> None:
        """校验 API Key 上传 scope。

        Cookie 用户用于内部 Web 工作台，首期先允许；API Key 系统间调用必须显式拥有
        ``file:upload``，避免普通问答 Key 默认获得文件上传能力。
        """
        if subject.api_key_id is None:
            return
        if "*" in subject.scopes or FILE_UPLOAD_SCOPE in subject.scopes:
            return
        raise ForbiddenError("api key scope does not allow file upload")

    @staticmethod
    def _extract_supported_file_type(filename: str) -> str:
        """从文件名提取并校验扩展名。"""
        suffix = PureWindowsPath(filename.strip()).suffix.lower()
        if suffix not in SUPPORTED_UPLOAD_EXTENSIONS:
            raise BadRequestError(
                "unsupported file type; supported types: pdf, doc, docx, png, jpg, jpeg"
            )
        return suffix.lstrip(".")

    @staticmethod
    def _resolve_content_type(filename: str, content_type: str | None) -> str:
        """确定上传 Content-Type。

        优先使用调用方显式传入的 MIME 类型；未传入时按文件名推断，无法推断则使用
        ``application/octet-stream``。
        """
        normalized = (content_type or "").strip()
        if normalized:
            return normalized
        guessed, _ = mimetypes.guess_type(filename)
        return guessed or DEFAULT_CONTENT_TYPE

    @classmethod
    def _build_object_key(cls, *, subject: AuthenticatedSubject, file_type: str) -> str:
        """生成对象存储 key。

        对象 key 不使用原始文件名，避免合同名称、客户名称等敏感信息进入存储路径。
        """
        owner = cls._owner_segment(subject)
        now = datetime.now(timezone.utc)
        return (
            f"uploads/{owner}/{now:%Y/%m/%d}/{uuid7()}.{file_type}"
        )

    @staticmethod
    def _owner_segment(subject: AuthenticatedSubject) -> str:
        raw_owner = subject.org_unit_id or subject.user_id or subject.api_key_id or "unassigned"
        safe_owner = _SAFE_OWNER_RE.sub("-", raw_owner).strip("-")
        return safe_owner or "unassigned"

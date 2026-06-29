from dataclasses import dataclass, field
from typing import Protocol
from urllib.parse import quote, unquote, urlparse

from app.integrations.object_storage.errors import ObjectStorageError


@dataclass(frozen=True)
class StoredFile:
    """对象存储文件定位信息。

    Attributes:
        bucket: 对象存储 bucket 名称。
        object_key: bucket 内的对象路径。
        storage_uri: 平台内部 URI，格式为 ``minio://bucket/object-key``。
        content_type: 文件 MIME 类型，未知时为空。
        size_bytes: 文件大小，未知时为空。
    """

    bucket: str
    object_key: str
    storage_uri: str
    content_type: str | None = None
    size_bytes: int | None = None


@dataclass(frozen=True)
class PresignedUrl:
    """预签名 URL 响应。

    Attributes:
        url: 可直接给调用方使用的临时 URL。
        method: HTTP 方法，上传通常为 ``PUT``，下载通常为 ``GET``。
        headers: 调用该 URL 时必须携带的 header，例如 ``Content-Type``。
        expires_seconds: URL 有效期秒数。
        storage_uri: 该 URL 对应的平台内部对象 URI。
    """

    url: str
    method: str
    headers: dict[str, str] = field(default_factory=dict)
    expires_seconds: int = 900
    storage_uri: str = ""


class FileStorage(Protocol):
    """对象存储统一协议。

    Boundary:
        业务模块只依赖本协议。底层可使用 MinIO、S3 或其它 S3 兼容对象存储，
        但 SDK 细节必须留在 ``integrations/object_storage`` 内部。
    """

    def upload_bytes(
        self,
        *,
        bucket: str,
        object_key: str,
        content: bytes,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> StoredFile:
        """上传字节内容。

        Args:
            bucket: 目标 bucket。
            object_key: 目标对象路径。
            content: 文件字节内容。
            content_type: MIME 类型。
            metadata: 对象元数据，SDK 会按 provider 规则写入。

        Returns:
            StoredFile: 已上传对象的内部定位信息。

        Raises:
            ObjectStorageError: 上传失败或 provider 返回异常。
        """

    def download_bytes(self, *, bucket: str, object_key: str) -> bytes:
        """下载对象字节内容。

        Args:
            bucket: 源 bucket。
            object_key: 源对象路径。

        Returns:
            bytes: 文件内容。

        Raises:
            ObjectStorageError: 下载失败或对象不存在。
        """

    def create_presigned_upload_url(
        self,
        *,
        bucket: str,
        object_key: str,
        content_type: str | None = None,
        expires_seconds: int | None = None,
    ) -> PresignedUrl:
        """生成预签名上传 URL。

        调用方拿到 URL 后使用 ``PUT`` 上传文件。若传入 ``content_type``，调用方必须
        在上传请求中携带相同 ``Content-Type``，否则 S3 签名校验可能失败。
        """

    def create_presigned_download_url(
        self,
        *,
        bucket: str,
        object_key: str,
        expires_seconds: int | None = None,
    ) -> PresignedUrl:
        """生成预签名下载 URL。"""


def build_storage_uri(bucket: str, object_key: str) -> str:
    """构造 AgentHub 内部对象 URI。

    Args:
        bucket: 对象存储 bucket。
        object_key: bucket 内对象路径。

    Returns:
        ``minio://bucket/object-key`` 格式的 URI。
    """
    normalized_key = object_key.lstrip("/")
    return f"minio://{bucket}/{quote(normalized_key, safe='/')}"


def parse_storage_uri(storage_uri: str) -> tuple[str, str]:
    """解析 AgentHub 内部对象 URI。

    Args:
        storage_uri: ``minio://bucket/object-key`` 格式 URI。

    Returns:
        ``(bucket, object_key)``。

    Raises:
        ObjectStorageError: URI scheme、bucket 或 object key 不合法。
    """
    parsed = urlparse(storage_uri)
    if parsed.scheme != "minio":
        raise ObjectStorageError("storage uri must use minio:// scheme")
    if not parsed.netloc:
        raise ObjectStorageError("storage uri missing bucket")
    object_key = unquote(parsed.path.lstrip("/"))
    if not object_key:
        raise ObjectStorageError("storage uri missing object key")
    return parsed.netloc, object_key

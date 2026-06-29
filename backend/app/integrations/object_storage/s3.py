from typing import Any

from app.core.config import Settings
from app.integrations.object_storage.base import (
    PresignedUrl,
    StoredFile,
    build_storage_uri,
)
from app.integrations.object_storage.errors import (
    ObjectStorageConfigurationError,
    ObjectStorageError,
)


class S3FileStorage:
    """S3 兼容对象存储实现。

    MinIO 兼容 S3 API，因此本实现可同时服务本地 MinIO、内网 MinIO 和未来可能的
    S3 兼容云对象存储。业务层不得直接使用 boto3，只能经由 ``FileStorage`` 抽象。
    """

    def __init__(self, *, settings: Settings, s3_client: Any | None = None):
        self.settings = settings
        self.default_expires_seconds = settings.object_storage_presign_expires_seconds
        self._client = s3_client or self._create_boto3_client(settings)

    def upload_bytes(
        self,
        *,
        bucket: str,
        object_key: str,
        content: bytes,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> StoredFile:
        """上传字节内容到 S3/MinIO。

        Args:
            bucket: 目标 bucket。
            object_key: 目标对象路径。
            content: 文件内容字节。
            content_type: MIME 类型。
            metadata: 对象元数据。

        Returns:
            StoredFile: 已上传对象定位信息。

        Raises:
            ObjectStorageError: SDK 调用失败时抛出统一异常。
        """
        params: dict[str, Any] = {
            "Bucket": bucket,
            "Key": object_key,
            "Body": content,
        }
        if content_type:
            params["ContentType"] = content_type
        if metadata:
            params["Metadata"] = metadata
        try:
            self._client.put_object(**params)
        except Exception as exc:
            raise ObjectStorageError("failed to upload object") from exc
        return StoredFile(
            bucket=bucket,
            object_key=object_key,
            storage_uri=build_storage_uri(bucket, object_key),
            content_type=content_type,
            size_bytes=len(content),
        )

    def download_bytes(self, *, bucket: str, object_key: str) -> bytes:
        """从 S3/MinIO 下载对象内容。

        Args:
            bucket: 源 bucket。
            object_key: 源对象路径。

        Returns:
            bytes: 文件内容。

        Raises:
            ObjectStorageError: SDK 调用失败或响应体不可读时抛出统一异常。
        """
        try:
            response = self._client.get_object(Bucket=bucket, Key=object_key)
            return response["Body"].read()
        except Exception as exc:
            raise ObjectStorageError("failed to download object") from exc

    def create_presigned_upload_url(
        self,
        *,
        bucket: str,
        object_key: str,
        content_type: str | None = None,
        expires_seconds: int | None = None,
    ) -> PresignedUrl:
        """生成 PUT 预签名上传 URL。"""
        effective_expires = expires_seconds or self.default_expires_seconds
        params = {"Bucket": bucket, "Key": object_key}
        headers: dict[str, str] = {}
        if content_type:
            params["ContentType"] = content_type
            headers["Content-Type"] = content_type
        try:
            url = self._client.generate_presigned_url(
                "put_object",
                Params=params,
                ExpiresIn=effective_expires,
                HttpMethod="PUT",
            )
        except Exception as exc:
            raise ObjectStorageError("failed to create presigned upload url") from exc
        return PresignedUrl(
            url=url,
            method="PUT",
            headers=headers,
            expires_seconds=effective_expires,
            storage_uri=build_storage_uri(bucket, object_key),
        )

    def create_presigned_download_url(
        self,
        *,
        bucket: str,
        object_key: str,
        expires_seconds: int | None = None,
    ) -> PresignedUrl:
        """生成 GET 预签名下载 URL。"""
        effective_expires = expires_seconds or self.default_expires_seconds
        try:
            url = self._client.generate_presigned_url(
                "get_object",
                Params={"Bucket": bucket, "Key": object_key},
                ExpiresIn=effective_expires,
                HttpMethod="GET",
            )
        except Exception as exc:
            raise ObjectStorageError("failed to create presigned download url") from exc
        return PresignedUrl(
            url=url,
            method="GET",
            expires_seconds=effective_expires,
            storage_uri=build_storage_uri(bucket, object_key),
        )

    @staticmethod
    def _create_boto3_client(settings: Settings) -> Any:
        """创建 boto3 S3 client。

        Raises:
            ObjectStorageConfigurationError: endpoint、access key 或 secret key 缺失。
        """
        if not settings.object_storage_endpoint:
            raise ObjectStorageConfigurationError("OBJECT_STORAGE_ENDPOINT is required")
        if not settings.object_storage_access_key:
            raise ObjectStorageConfigurationError("OBJECT_STORAGE_ACCESS_KEY is required")
        if not settings.object_storage_secret_key:
            raise ObjectStorageConfigurationError("OBJECT_STORAGE_SECRET_KEY is required")

        try:
            import boto3
            from botocore.config import Config
        except ImportError as exc:
            raise ObjectStorageConfigurationError("boto3 is required for object storage") from exc

        return boto3.client(
            "s3",
            endpoint_url=settings.object_storage_endpoint,
            aws_access_key_id=settings.object_storage_access_key,
            aws_secret_access_key=settings.object_storage_secret_key,
            region_name=settings.object_storage_region,
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
            ),
        )

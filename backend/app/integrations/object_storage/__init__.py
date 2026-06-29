"""对象存储集成模块。

业务层只能依赖 ``FileStorage`` 抽象和 ``create_file_storage`` 工厂，不应直接
import boto3、minio-py 或任何具体对象存储 SDK。
"""

from app.integrations.object_storage.base import (
    FileStorage,
    PresignedUrl,
    StoredFile,
    build_storage_uri,
    parse_storage_uri,
)
from app.integrations.object_storage.errors import (
    ObjectStorageConfigurationError,
    ObjectStorageError,
)
from app.integrations.object_storage.factory import create_file_storage

__all__ = [
    "FileStorage",
    "ObjectStorageConfigurationError",
    "ObjectStorageError",
    "PresignedUrl",
    "StoredFile",
    "build_storage_uri",
    "create_file_storage",
    "parse_storage_uri",
]

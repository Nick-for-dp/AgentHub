from fastapi import status

from app.core.exceptions import AgentHubError


class ObjectStorageError(AgentHubError):
    """对象存储通用异常。

    对外不暴露底层 SDK 的异常类型，避免业务层绑定 boto3/minio-py，也避免错误响应中
    泄漏 endpoint、access key 等敏感配置。
    """

    def __init__(self, message: str = "object storage error"):
        super().__init__(
            "OBJECT_STORAGE_ERROR",
            message,
            status.HTTP_502_BAD_GATEWAY,
        )


class ObjectStorageConfigurationError(ObjectStorageError):
    """对象存储配置缺失或不合法。"""

    def __init__(self, message: str = "object storage is not configured"):
        AgentHubError.__init__(
            self,
            "OBJECT_STORAGE_NOT_CONFIGURED",
            message,
            status.HTTP_503_SERVICE_UNAVAILABLE,
        )

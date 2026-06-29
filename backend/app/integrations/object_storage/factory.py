from app.core.config import Settings, get_settings
from app.integrations.object_storage.base import FileStorage
from app.integrations.object_storage.s3 import S3FileStorage


def create_file_storage(settings: Settings | None = None) -> FileStorage:
    """创建对象存储实现。

    Args:
        settings: 应用配置。测试可传入显式配置，生产默认读取环境变量。

    Returns:
        FileStorage: 当前统一使用 S3 兼容实现，可连接 MinIO。
    """
    return S3FileStorage(settings=settings or get_settings())

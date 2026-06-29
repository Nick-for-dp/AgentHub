from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.datetime import BeijingDateTime
from app.core.enums import FileParseTaskStatus


class FileParseTaskCreate(BaseModel):
    """创建文件解析任务请求。

    Args:
        source_uri: 上传接口返回的对象存储 URI，例如
            ``minio://int-agenthub-raw/uploads/org/2026/06/29/xxx.docx``。
    """

    source_uri: str = Field(min_length=1, max_length=500)


class FileParseTaskRead(BaseModel):
    """文件解析任务响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    owner_org_unit_id: str | None
    created_by: str | None
    api_key_id: str | None
    source_uri: str
    file_type: str
    reader_type: str | None
    status: FileParseTaskStatus
    result_snapshot: dict[str, Any] | None = None
    error_message: str | None = None
    created_at: BeijingDateTime
    updated_at: BeijingDateTime
    finished_at: BeijingDateTime | None = None

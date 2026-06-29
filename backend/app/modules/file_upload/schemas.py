from pydantic import BaseModel, Field


class FileUploadPrepareRequest(BaseModel):
    """生成预签名上传 URL 的请求。

    Args:
        filename: 调用方侧原始文件名，仅用于提取扩展名和前端展示；对象存储 key 不直接
            使用该文件名，避免路径穿越和敏感业务信息进入对象路径。
        content_type: 上传时使用的 MIME 类型。若为空，后端会按文件扩展名做保守推断。
        file_size_bytes: 调用方声明的文件大小，首期仅用于后续审计和限额预留。
    """

    filename: str = Field(min_length=1, max_length=255)
    content_type: str | None = Field(default=None, max_length=255)
    file_size_bytes: int | None = Field(default=None, gt=0)


class FileUploadPrepareResponse(BaseModel):
    """预签名上传 URL 响应。

    调用方按 ``method`` 和 ``headers`` 上传文件到 ``upload_url``。上传成功后，
    后续创建解析任务时传入 ``storage_uri``。
    """

    upload_url: str
    method: str
    headers: dict[str, str] = Field(default_factory=dict)
    storage_uri: str
    bucket: str
    object_key: str
    original_filename: str
    file_type: str
    content_type: str
    expires_seconds: int

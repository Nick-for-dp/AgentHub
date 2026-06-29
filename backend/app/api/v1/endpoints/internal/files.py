from fastapi import APIRouter, Depends

from app.core.responses import APIResponse, success
from app.modules.auth.dependencies import get_current_subject
from app.modules.auth.schemas import AuthenticatedSubject
from app.modules.file_upload.schemas import (
    FileUploadPrepareRequest,
    FileUploadPrepareResponse,
)
from app.modules.file_upload.service import FileUploadService

router = APIRouter()


def get_file_upload_service() -> FileUploadService:
    """构造文件上传服务。

    独立 dependency 便于测试时注入 fake storage/service；真实运行时由 service 内部读取
    配置并创建对象存储客户端。
    """
    return FileUploadService()


@router.post("/upload", response_model=APIResponse[FileUploadPrepareResponse])
def prepare_file_upload(
    payload: FileUploadPrepareRequest,
    subject: AuthenticatedSubject = Depends(get_current_subject),
    service: FileUploadService = Depends(get_file_upload_service),
) -> APIResponse[FileUploadPrepareResponse]:
    """生成内部文件预签名上传 URL。

    上传接口只负责授权和生成对象存储 URL，不创建解析任务，也不写调用记录。调用方
    上传成功后，应把 ``storage_uri`` 传给后续 file_parse_task 创建接口。
    """
    return success(service.prepare_upload(payload=payload, subject=subject))

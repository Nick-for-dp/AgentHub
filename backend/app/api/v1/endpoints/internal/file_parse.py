from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.responses import APIResponse, success
from app.db.session import get_db
from app.modules.auth.dependencies import get_current_subject
from app.modules.auth.schemas import AuthenticatedSubject
from app.modules.file_parse.schemas import FileParseTaskCreate, FileParseTaskRead
from app.modules.file_parse.service import FileParseService

router = APIRouter()


def get_file_parse_service(db: Session = Depends(get_db)) -> FileParseService:
    """构造文件解析服务。

    独立 dependency 便于测试覆盖 storage/parser；生产默认使用 MinIO FileStorage 和
    当前 file_reader factory。
    """
    return FileParseService(db)


@router.post("/tasks", response_model=APIResponse[FileParseTaskRead])
async def create_file_parse_task(
    payload: FileParseTaskCreate,
    subject: AuthenticatedSubject = Depends(get_current_subject),
    service: FileParseService = Depends(get_file_parse_service),
) -> APIResponse[FileParseTaskRead]:
    """创建并执行文件解析任务。

    MVP 阶段同步执行解析，但 API 契约保持任务形态；上传、解析、查询本身不写
    ``agent_invocation_record``。
    """
    task = await service.create_task(payload=payload, subject=subject)
    return success(FileParseTaskRead.model_validate(task))


@router.get("/tasks/{task_id}", response_model=APIResponse[FileParseTaskRead])
def get_file_parse_task(
    task_id: str,
    subject: AuthenticatedSubject = Depends(get_current_subject),
    service: FileParseService = Depends(get_file_parse_service),
) -> APIResponse[FileParseTaskRead]:
    """查询文件解析任务。"""
    task = service.get_task(task_id=task_id, subject=subject)
    return success(FileParseTaskRead.model_validate(task))


@router.post("/tasks/{task_id}/cancel", response_model=APIResponse[FileParseTaskRead])
def cancel_file_parse_task(
    task_id: str,
    subject: AuthenticatedSubject = Depends(get_current_subject),
    service: FileParseService = Depends(get_file_parse_service),
) -> APIResponse[FileParseTaskRead]:
    """取消文件解析任务。"""
    task = service.cancel_task(task_id=task_id, subject=subject)
    return success(FileParseTaskRead.model_validate(task))

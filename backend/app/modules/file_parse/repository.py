from sqlalchemy.orm import Session

from app.modules.file_parse.models import FileParseTask


class FileParseTaskRepository:
    """文件解析任务数据访问层。"""

    def __init__(self, db: Session):
        self.db = db

    def add_task(self, task: FileParseTask) -> None:
        """添加解析任务到当前 session。"""
        self.db.add(task)

    def get_task(self, task_id: str) -> FileParseTask | None:
        """按 ID 查询解析任务。"""
        return self.db.get(FileParseTask, task_id)

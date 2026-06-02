"""调用记录业务服务。

负责调用记录的创建、完成更新、筛选查询。
调用记录同时服务于两个视角：
- 业务视角：用户/客户 Q&A 历史
- 技术视角：Agent 调用审计、故障排查、质量评估
"""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.modules.agent.repository import AgentRepository
from app.modules.invocation.models import AgentInvocationRecord
from app.modules.invocation.repository import InvocationRepository
from app.modules.invocation.schemas import (
    InvocationRecordCreate,
    InvocationRecordFilter,
    InvocationRecordFinish,
)


class InvocationService:
    """调用记录服务。

    提供：
    - create_record: 调用开始时创建 PENDING 记录
    - finish_record: 调用结束时更新状态、输出、耗时
    - list_records: 筛选分页查询
    """

    def __init__(self, db: Session):
        self.db = db
        self.repository = InvocationRepository(db)
        self.agent_repository = AgentRepository(db)

    def create_record(self, payload: InvocationRecordCreate) -> AgentInvocationRecord:
        """在 Agent 调用开始时创建调用记录。

        初始状态为 PENDING，调用结束后由 finish_record 更新。
        """
        record = AgentInvocationRecord(**payload.model_dump())
        self.repository.add_record(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def finish_record(
        self,
        record_id: str,
        payload: InvocationRecordFinish,
    ) -> AgentInvocationRecord:
        """更新调用记录的最终状态。

        填充输出内容、成功/失败状态、错误信息、耗时、快照字段。
        同时写入 finished_at 时间戳（用于计算调用耗时）。
        """
        record = self.repository.get_record(record_id)
        if record is None:
            raise NotFoundError("invocation record not found")
        for field, value in payload.model_dump().items():
            setattr(record, field, value)
        record.finished_at = datetime.now(timezone.utc)
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def list_records(self, filters: InvocationRecordFilter) -> tuple[list[AgentInvocationRecord], int]:
        """按筛选条件分页查询调用记录。

        支持按 Agent（ID 或 code）、状态、API Key、时间范围筛选。
        如果传入 agent_code，先查 Agent 表转换为 agent_id 再筛选。
        """
        agent_id = filters.agent_id
        # agent_code → agent_id 转换（agent_code 是面向外部客户的稳定标识）
        if filters.agent_code and not agent_id:
            agent = self.agent_repository.get_agent_by_code(filters.agent_code)
            if agent:
                agent_id = agent.id
            else:
                # Agent code 不存在时返回空结果
                return [], 0

        return self.repository.list_records(
            agent_id=agent_id,
            status=filters.status.value if filters.status else None,
            api_key_id=filters.api_key_id,
            created_from=filters.created_from,
            created_to=filters.created_to,
            page=filters.page,
            page_size=filters.page_size,
        )

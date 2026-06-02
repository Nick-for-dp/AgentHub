"""调用记录查询 API。

管理端可按 Agent、状态、时间范围、API Key 等多维筛选调用记录，
并支持分页。每一条记录是平台审计的原子事实。
"""

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import InvocationStatus
from app.core.responses import APIResponse, success
from app.db.session import get_db
from app.modules.agent.models import Agent
from app.modules.auth.models import APIKey
from app.modules.invocation.schemas import InvocationRecordFilter, InvocationRecordPage, InvocationRecordRead
from app.modules.invocation.service import InvocationService
from app.modules.org.models import OrgUnit, UserAccount

router = APIRouter()


@router.get("", response_model=APIResponse[InvocationRecordPage])
def list_invocation_records(
    agent_id: str | None = Query(default=None, description="Agent ID"),
    agent_code: str | None = Query(default=None, description="Agent code"),
    status: InvocationStatus | None = Query(default=None, description="调用状态"),
    api_key_id: str | None = Query(default=None, description="API Key ID"),
    # 时间参数使用 datetime 类型，让 FastAPI/Pydantic 自动完成 ISO 8601 字符串解析。
    # 如果客户端传入非法时间格式（如 "abc"），Pydantic 会自动返回 422 校验错误，
    # 而不会像手动 fromisoformat 那样抛出 500。
    created_from: datetime | None = Query(default=None, description="创建时间起始（ISO 8601）"),
    created_to: datetime | None = Query(default=None, description="创建时间截止（ISO 8601）"),
    page: int = Query(default=1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页条数"),
    db: Session = Depends(get_db),
) -> APIResponse[InvocationRecordPage]:
    """查询调用记录列表，支持多维筛选和分页。

    所有筛选条件均为可选，不填则不筛选。
    时间参数使用 ISO 8601 格式，例如 "2026-05-19T00:00:00"。
    """

    # 构造筛选对象（时间字段已是 datetime 对象，直接传入）
    filters = InvocationRecordFilter(
        agent_id=agent_id,
        agent_code=agent_code,
        status=status,
        api_key_id=api_key_id,
        created_from=created_from,
        created_to=created_to,
        page=page,
        page_size=page_size,
    )

    items, total = InvocationService(db).list_records(filters)
    enriched_items = _build_invocation_reads(db, items)
    return success(InvocationRecordPage(
        items=enriched_items,
        total=total,
        page=page,
        page_size=page_size,
    ))


def _build_invocation_reads(db: Session, items: list) -> list[InvocationRecordRead]:
    """Build list DTOs with display fields needed by the admin UI."""
    agent_ids = {item.agent_id for item in items if item.agent_id}
    user_ids = {item.user_id for item in items if item.user_id}
    org_ids = {item.org_unit_id for item in items if item.org_unit_id}
    api_key_ids = {item.api_key_id for item in items if item.api_key_id}

    agents = {
        agent.id: agent
        for agent in db.scalars(select(Agent).where(Agent.id.in_(agent_ids))).all()
    } if agent_ids else {}
    users = {
        user.id: user
        for user in db.scalars(select(UserAccount).where(UserAccount.id.in_(user_ids))).all()
    } if user_ids else {}
    orgs = {
        org.id: org
        for org in db.scalars(select(OrgUnit).where(OrgUnit.id.in_(org_ids))).all()
    } if org_ids else {}
    api_keys = {
        api_key.id: api_key
        for api_key in db.scalars(select(APIKey).where(APIKey.id.in_(api_key_ids))).all()
    } if api_key_ids else {}

    result: list[InvocationRecordRead] = []
    for item in items:
        record = InvocationRecordRead.model_validate(item)
        agent = agents.get(item.agent_id)
        user = users.get(item.user_id) if item.user_id else None
        org = orgs.get(item.org_unit_id) if item.org_unit_id else None
        api_key = api_keys.get(item.api_key_id) if item.api_key_id else None
        record.agent_code = agent.code if agent else None
        record.agent_name = agent.name if agent else None
        record.org_unit_name = org.name if org else None
        record.customer_name = user.name if user else None
        record.customer_phone = user.phone_normalized if user else api_key.issued_for_phone if api_key else None
        record.api_key_name = api_key.name if api_key else None
        record.api_key_prefix = api_key.key_prefix if api_key else None
        result.append(record)
    return result

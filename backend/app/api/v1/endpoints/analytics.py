"""管理端运营分析 API。

基于现有事实表（conversation / conversation_message / lead_capture_event）
提供 DAU、用户消息数、聊天活跃跨度、业务追问次数等只读统计指标。
不新增埋点表和独立事件表。
"""

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.responses import APIResponse, success
from app.db.session import get_db
from app.modules.analytics.schemas import (
    AgentBusinessFollowupPage,
    DAUItem,
    UserChatDurationPage,
    UserMessageCountPage,
)
from app.modules.analytics.service import AnalyticsService

router = APIRouter()


@router.get("/daily-active-users", response_model=APIResponse[list[DAUItem]])
def daily_active_users(
    created_from: datetime | None = Query(default=None, description="统计起始时间（ISO 8601）"),
    created_to: datetime | None = Query(default=None, description="统计截止时间（ISO 8601）"),
    agent_code: str | None = Query(default=None, description="按 Agent 过滤"),
    user_id: str | None = Query(default=None, description="按用户过滤"),
    org_unit_id: str | None = Query(default=None, description="按组织过滤"),
    db: Session = Depends(get_db),
) -> APIResponse[list[DAUItem]]:
    """日活跃用户数趋势。

    口径：某自然日内发送过 USER 消息的唯一 user_id 数。
    """
    items = AnalyticsService(db).daily_active_users(
        created_from=created_from,
        created_to=created_to,
        agent_code=agent_code,
        user_id=user_id,
        org_unit_id=org_unit_id,
    )
    return success(items)


@router.get("/user-message-counts", response_model=APIResponse[UserMessageCountPage])
def user_message_counts(
    created_from: datetime | None = Query(default=None, description="统计起始时间（ISO 8601）"),
    created_to: datetime | None = Query(default=None, description="统计截止时间（ISO 8601）"),
    agent_code: str | None = Query(default=None, description="按 Agent 过滤"),
    user_id: str | None = Query(default=None, description="按用户过滤"),
    org_unit_id: str | None = Query(default=None, description="按组织过滤"),
    page: int = Query(default=1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页条数"),
    db: Session = Depends(get_db),
) -> APIResponse[UserMessageCountPage]:
    """用户消息发送次数排行。

    展示：用户名称、手机号、组织、消息数、最近发送时间、关联 Agent。
    """
    result = AnalyticsService(db).user_message_counts(
        created_from=created_from,
        created_to=created_to,
        agent_code=agent_code,
        user_id=user_id,
        org_unit_id=org_unit_id,
        page=page,
        page_size=page_size,
    )
    return success(result)


@router.get("/user-chat-duration", response_model=APIResponse[UserChatDurationPage])
def user_chat_duration(
    created_from: datetime | None = Query(default=None, description="统计起始时间（ISO 8601）"),
    created_to: datetime | None = Query(default=None, description="统计截止时间（ISO 8601）"),
    agent_code: str | None = Query(default=None, description="按 Agent 过滤"),
    user_id: str | None = Query(default=None, description="按用户过滤"),
    org_unit_id: str | None = Query(default=None, description="按组织过滤"),
    page: int = Query(default=1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页条数"),
    db: Session = Depends(get_db),
) -> APIResponse[UserChatDurationPage]:
    """用户聊天活跃跨度排行。

    口径：按用户/自然日统计聊天消息时间跨度（首末消息时间差），
    需要至少 2 条消息才能估算。管理端应注明为"根据聊天消息时间估算"。
    """
    result = AnalyticsService(db).user_chat_duration(
        created_from=created_from,
        created_to=created_to,
        agent_code=agent_code,
        user_id=user_id,
        org_unit_id=org_unit_id,
        page=page,
        page_size=page_size,
    )
    return success(result)


@router.get("/agent-business-followups", response_model=APIResponse[AgentBusinessFollowupPage])
def agent_business_followups(
    created_from: datetime | None = Query(default=None, description="统计起始时间（ISO 8601）"),
    created_to: datetime | None = Query(default=None, description="统计截止时间（ISO 8601）"),
    agent_code: str | None = Query(default=None, description="按 Agent 过滤"),
    user_id: str | None = Query(default=None, description="按用户过滤"),
    org_unit_id: str | None = Query(default=None, description="按组织过滤"),
    page: int = Query(default=1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页条数"),
    db: Session = Depends(get_db),
) -> APIResponse[AgentBusinessFollowupPage]:
    """智能体业务追问次数统计。

    数据源：lead_capture_event.followup_decision.should_ask_followup = true。
    展示命名为"智能体业务追问次数"或"促转化触达次数"。
    """
    result = AnalyticsService(db).agent_business_followups(
        created_from=created_from,
        created_to=created_to,
        agent_code=agent_code,
        user_id=user_id,
        org_unit_id=org_unit_id,
        page=page,
        page_size=page_size,
    )
    return success(result)

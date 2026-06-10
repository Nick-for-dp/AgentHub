"""AnalyticsService — 基于现有事实表的只读运营统计。

所有指标均从 conversation / conversation_message / lead_capture_event 等事实表计算，
不新增埋点表和独立事件表。
"""

from datetime import date, datetime, timedelta
from typing import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.agent.models import Agent
from app.modules.conversation.models import Conversation, ConversationMessage
from app.modules.lead.models import LeadCaptureEvent
from app.modules.org.models import OrgUnit, UserAccount

from .schemas import (
    AgentBusinessFollowupItem,
    AgentBusinessFollowupPage,
    DAUItem,
    UserChatDurationItem,
    UserChatDurationPage,
    UserMessageCountItem,
    UserMessageCountPage,
)


class AnalyticsService:
    """只读运营统计服务，不修改任何事实表。"""

    def __init__(self, db: Session):
        self.db = db

    # ── 日活用户数 (DAU) ──────────────────────────────────────────

    def daily_active_users(
        self,
        *,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        agent_code: str | None = None,
        user_id: str | None = None,
        org_unit_id: str | None = None,
    ) -> list[DAUItem]:
        """按自然日统计发送过用户消息的唯一 user_id 数。

        数据源：conversation_message(role='USER') JOIN conversation。
        """
        date_col = func.date(ConversationMessage.created_at)
        stmt = (
            select(
                date_col.label("date"),
                func.count(func.distinct(Conversation.user_id)).label("active_users"),
            )
            .select_from(ConversationMessage)
            .join(Conversation, Conversation.id == ConversationMessage.conversation_id)
            .where(ConversationMessage.role == "USER")
        )
        stmt = self._apply_conversation_filters(
            stmt=stmt,
            created_from=created_from,
            created_to=created_to,
            agent_code=agent_code,
            user_id=user_id,
            org_unit_id=org_unit_id,
            message_date_col=ConversationMessage.created_at,
        )
        stmt = stmt.group_by(date_col).order_by(date_col.asc())

        rows = self.db.execute(stmt).all()
        counts_by_date = {
            self._date_key(row.date): row.active_users
            for row in rows
        }
        if created_from is not None and created_to is not None:
            return [
                DAUItem(date=day.isoformat(), active_users=counts_by_date.get(day.isoformat(), 0))
                for day in self._iter_dates(created_from.date(), created_to.date())
            ]
        return [
            DAUItem(date=self._date_key(row.date), active_users=row.active_users)
            for row in rows
        ]

    # ── 用户消息发送次数 ─────────────────────────────────────────

    def user_message_counts(
        self,
        *,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        agent_code: str | None = None,
        user_id: str | None = None,
        org_unit_id: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> UserMessageCountPage:
        """统计每个用户发送 USER 消息的数量，按消息数降序。

        展示字段：用户名称、手机号、组织、消息数、最近发送时间、关联 Agent。
        """
        stmt = (
            select(
                Conversation.user_id,
                func.count(ConversationMessage.id).label("message_count"),
                func.max(ConversationMessage.created_at).label("last_message_at"),
            )
            .select_from(ConversationMessage)
            .join(Conversation, Conversation.id == ConversationMessage.conversation_id)
            .where(ConversationMessage.role == "USER")
        )
        stmt = self._apply_conversation_filters(
            stmt=stmt,
            created_from=created_from,
            created_to=created_to,
            agent_code=agent_code,
            user_id=user_id,
            org_unit_id=org_unit_id,
            message_date_col=ConversationMessage.created_at,
        )
        stmt = stmt.group_by(Conversation.user_id)

        # 先查总数
        total = self.db.scalar(
            select(func.count()).select_from(stmt.subquery())
        ) or 0

        # 排序 + 分页
        stmt = stmt.order_by(func.count(ConversationMessage.id).desc())
        offset = (page - 1) * page_size
        stmt = stmt.limit(page_size).offset(offset)
        rows = self.db.execute(stmt).all()

        # 批量获取用户、组织、Agent 信息
        user_ids = {row.user_id for row in rows if row.user_id}
        users_map = self._batch_users(user_ids)
        orgs_map = self._batch_orgs_for_users(users_map)
        agent_codes_map = self._batch_agent_codes_for_users(
            user_ids,
            created_from,
            created_to,
            agent_code,
        )

        items: list[UserMessageCountItem] = []
        for row in rows:
            user = users_map.get(row.user_id)
            items.append(
                UserMessageCountItem(
                    user_id=row.user_id,
                    user_name=user.name if user else None,
                    phone_normalized=user.phone_normalized if user else None,
                    org_unit_name=orgs_map.get(user.org_unit_id) if user else None,
                    message_count=row.message_count,
                    last_message_at=row.last_message_at,
                    agent_codes=sorted(agent_codes_map.get(row.user_id, set())),
                )
            )
        return UserMessageCountPage(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )

    # ── 用户聊天活跃跨度 ─────────────────────────────────────────

    def user_chat_duration(
        self,
        *,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        agent_code: str | None = None,
        user_id: str | None = None,
        org_unit_id: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> UserChatDurationPage:
        """按用户/自然日统计聊天消息时间跨度（需要至少 2 条消息才能估算）。

        说明：该指标根据聊天消息时间估算，不是严格页面停留时长。
        """
        date_col = func.date(ConversationMessage.created_at)
        stmt = (
            select(
                Conversation.user_id,
                date_col.label("chat_date"),
                func.min(ConversationMessage.created_at).label("first_message_at"),
                func.max(ConversationMessage.created_at).label("last_message_at"),
                func.count(ConversationMessage.id).label("message_count"),
            )
            .select_from(ConversationMessage)
            .join(Conversation, Conversation.id == ConversationMessage.conversation_id)
            .where(ConversationMessage.role == "USER")
        )
        stmt = self._apply_conversation_filters(
            stmt=stmt,
            created_from=created_from,
            created_to=created_to,
            agent_code=agent_code,
            user_id=user_id,
            org_unit_id=org_unit_id,
            message_date_col=ConversationMessage.created_at,
        )
        stmt = stmt.group_by(Conversation.user_id, date_col)
        # 至少需要 2 条消息才能估算跨度
        stmt = stmt.having(func.count(ConversationMessage.id) >= 2)

        # 先查总数
        total = self.db.scalar(
            select(func.count()).select_from(stmt.subquery())
        ) or 0

        # 按时长降序
        duration_expr = func.max(ConversationMessage.created_at) - func.min(ConversationMessage.created_at)
        stmt = stmt.order_by(duration_expr.desc())
        offset = (page - 1) * page_size
        stmt = stmt.limit(page_size).offset(offset)
        rows = self.db.execute(stmt).all()

        # 批量获取用户名
        user_ids = {row.user_id for row in rows if row.user_id}
        users_map = self._batch_users(user_ids)

        items: list[UserChatDurationItem] = []
        for row in rows:
            user = users_map.get(row.user_id)
            delta = row.last_message_at - row.first_message_at
            duration_seconds = int(delta.total_seconds()) if delta else 0
            items.append(
                UserChatDurationItem(
                    user_id=row.user_id,
                    user_name=user.name if user else None,
                    chat_date=str(row.chat_date),
                    first_message_at=row.first_message_at,
                    last_message_at=row.last_message_at,
                    duration_seconds=duration_seconds,
                    message_count=row.message_count,
                )
            )
        return UserChatDurationPage(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )

    # ── 智能体业务追问次数 ───────────────────────────────────────

    def agent_business_followups(
        self,
        *,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        agent_code: str | None = None,
        user_id: str | None = None,
        org_unit_id: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> AgentBusinessFollowupPage:
        """统计 followup_decision.should_ask_followup=true 的次数。

        数据源：lead_capture_event.followup_decision（JSON 字段）。
        JSON 过滤在 Python 层完成，确保 SQLite / PostgreSQL 兼容。
        """
        stmt = select(LeadCaptureEvent)
        if created_from is not None:
            stmt = stmt.where(LeadCaptureEvent.created_at >= created_from)
        if created_to is not None:
            stmt = stmt.where(LeadCaptureEvent.created_at <= created_to)
        if agent_code is not None:
            stmt = stmt.where(LeadCaptureEvent.agent_code == agent_code)
        if user_id is not None:
            stmt = stmt.where(LeadCaptureEvent.user_id == user_id)
        if org_unit_id is not None:
            stmt = stmt.where(LeadCaptureEvent.org_unit_id == org_unit_id)

        all_events = self.db.scalars(stmt).all()

        # Python 层过滤 followup_decision.should_ask_followup == true
        followup_events = [
            e for e in all_events
            if self._is_should_ask_followup(e.followup_decision)
        ]

        # 按 agent_code 聚合计数
        counter: dict[str, int] = {}
        for event in followup_events:
            code = event.agent_code or "__unknown__"
            counter[code] = counter.get(code, 0) + 1

        # 排序 + 分页
        sorted_items = sorted(counter.items(), key=lambda x: x[1], reverse=True)
        total = len(sorted_items)
        offset = (page - 1) * page_size
        page_items = sorted_items[offset : offset + page_size]

        # 批量获取 Agent 名称
        agent_codes = {code for code, _ in page_items}
        agents_map = self._batch_agents(agent_codes)

        items = [
            AgentBusinessFollowupItem(
                agent_code=code,
                agent_name=agents_map.get(code).name if agents_map.get(code) else None,
                followup_count=count,
            )
            for code, count in page_items
        ]
        return AgentBusinessFollowupPage(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )

    # ── 筛选条件复用 ──────────────────────────────────────────────

    def _apply_conversation_filters(self, *, stmt, created_from, created_to,
                                    agent_code, user_id, org_unit_id,
                                    message_date_col):
        """为 conversation_message JOIN conversation 查询统一施加筛选条件。"""
        if created_from is not None:
            stmt = stmt.where(message_date_col >= created_from)
        if created_to is not None:
            stmt = stmt.where(message_date_col <= created_to)
        if agent_code is not None:
            stmt = stmt.where(Conversation.agent_code == agent_code)
        if user_id is not None:
            stmt = stmt.where(Conversation.user_id == user_id)
        if org_unit_id is not None:
            stmt = stmt.where(Conversation.org_unit_id == org_unit_id)
        return stmt

    # ── 批量加载辅助方法 ──────────────────────────────────────────

    def _batch_users(self, user_ids: set[str]) -> dict[str, UserAccount]:
        if not user_ids:
            return {}
        users = self.db.scalars(
            select(UserAccount).where(UserAccount.id.in_(user_ids))
        ).all()
        return {u.id: u for u in users}

    def _batch_orgs_for_users(self, users_map: dict[str, UserAccount]) -> dict[str, str]:
        """返回 {org_unit_id: org_name} 映射。"""
        org_ids = {u.org_unit_id for u in users_map.values() if u.org_unit_id}
        if not org_ids:
            return {}
        orgs = self.db.scalars(
            select(OrgUnit).where(OrgUnit.id.in_(org_ids))
        ).all()
        return {o.id: o.name for o in orgs}

    def _batch_agent_codes_for_users(
        self,
        user_ids: set[str],
        created_from: datetime | None,
        created_to: datetime | None,
        agent_code: str | None,
    ) -> dict[str, set[str]]:
        """返回 {user_id: {agent_code, ...}} 映射，表示用户在时间范围内的关联 Agent。"""
        if not user_ids:
            return {}
        stmt = (
            select(Conversation.user_id, Conversation.agent_code)
            .select_from(ConversationMessage)
            .join(Conversation, Conversation.id == ConversationMessage.conversation_id)
            .where(
                ConversationMessage.role == "USER",
                Conversation.user_id.in_(user_ids),
            )
        )
        if created_from is not None:
            stmt = stmt.where(ConversationMessage.created_at >= created_from)
        if created_to is not None:
            stmt = stmt.where(ConversationMessage.created_at <= created_to)
        if agent_code is not None:
            stmt = stmt.where(Conversation.agent_code == agent_code)
        rows = self.db.execute(stmt.distinct()).all()
        result: dict[str, set[str]] = {}
        for row in rows:
            if row.user_id not in result:
                result[row.user_id] = set()
            if row.agent_code:
                result[row.user_id].add(row.agent_code)
        return result

    @staticmethod
    def _date_key(value) -> str:
        if isinstance(value, date):
            return value.isoformat()
        return str(value)

    @staticmethod
    def _iter_dates(start: date, end: date):
        current = start
        while current <= end:
            yield current
            current += timedelta(days=1)

    def _batch_agents(self, agent_codes: set[str]) -> dict[str, Agent]:
        if not agent_codes:
            return {}
        agents = self.db.scalars(
            select(Agent).where(Agent.code.in_(agent_codes))
        ).all()
        return {a.code: a for a in agents}

    @staticmethod
    def _is_should_ask_followup(followup_decision: dict) -> bool:
        """归一化 followup_decision 中的 should_ask_followup 字段为 bool。

        Dify 输出可能是 bool 或字符串 "True"/"False"。
        """
        if not isinstance(followup_decision, dict):
            return False
        value = followup_decision.get("should_ask_followup")
        if value is True:
            return True
        if isinstance(value, str):
            return value.lower() in ("true", "1", "yes")
        return False

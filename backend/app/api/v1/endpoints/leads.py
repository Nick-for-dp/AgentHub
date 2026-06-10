"""Admin lead query API.

This endpoint is read-only: Dify suggests lead deltas, LeadService owns writes,
and admins use this API to inspect/search the resulting lead facts.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.enums import LeadStatus
from app.core.responses import APIResponse, success
from app.db.session import get_db
from app.modules.agent.models import Agent
from app.modules.lead.models import LeadCaptureEvent, SalesLead
from app.modules.lead.repository import LeadRepository
from app.modules.lead.schemas import LeadCaptureEventRead, SalesLeadPage, SalesLeadRead
from app.modules.org.models import OrgUnit

router = APIRouter()


@router.get("", response_model=APIResponse[SalesLeadPage])
def list_sales_leads(
    keyword: str | None = Query(default=None, description="关键词，匹配需求、地区、联系人、公司、电话等"),
    status: LeadStatus | None = Query(default=None, description="线索状态"),
    created_from: datetime | None = Query(default=None, description="创建时间起始（ISO 8601）"),
    created_to: datetime | None = Query(default=None, description="创建时间截止（ISO 8601）"),
    page: int = Query(default=1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页条数"),
    db: Session = Depends(get_db),
) -> APIResponse[SalesLeadPage]:
    items, total = LeadRepository(db).list_sales_leads(
        keyword=keyword,
        status=status.value if status else None,
        created_from=created_from,
        created_to=created_to,
        page=page,
        page_size=page_size,
    )
    return success(
        SalesLeadPage(
            items=_build_lead_reads(db, items),
            total=total,
            page=page,
            page_size=page_size,
        )
    )


def _build_lead_reads(db: Session, items: list[SalesLead]) -> list[SalesLeadRead]:
    agent_ids = {item.agent_id for item in items if item.agent_id}
    org_ids = {item.org_unit_id for item in items if item.org_unit_id}
    lead_ids = {item.id for item in items}

    agents = {
        agent.id: agent
        for agent in db.scalars(select(Agent).where(Agent.id.in_(agent_ids))).all()
    } if agent_ids else {}
    orgs = {
        org.id: org
        for org in db.scalars(select(OrgUnit).where(OrgUnit.id.in_(org_ids))).all()
    } if org_ids else {}

    latest_events: dict[str, LeadCaptureEvent] = {}
    event_counts: dict[str, int] = {}
    if lead_ids:
        events = db.scalars(
            select(LeadCaptureEvent)
            .where(LeadCaptureEvent.sales_lead_id.in_(lead_ids))
            .order_by(LeadCaptureEvent.created_at.desc())
        ).all()
        for event in events:
            if event.sales_lead_id and event.sales_lead_id not in latest_events:
                latest_events[event.sales_lead_id] = event

        count_rows = db.execute(
            select(LeadCaptureEvent.sales_lead_id, func.count())
            .where(LeadCaptureEvent.sales_lead_id.in_(lead_ids))
            .group_by(LeadCaptureEvent.sales_lead_id)
        ).all()
        event_counts = {lead_id: count for lead_id, count in count_rows if lead_id}

    result: list[SalesLeadRead] = []
    for item in items:
        contact = item.contact
        agent = agents.get(item.agent_id) if item.agent_id else None
        org = orgs.get(item.org_unit_id) if item.org_unit_id else None
        latest_event = latest_events.get(item.id)
        result.append(
            SalesLeadRead(
                id=item.id,
                contact_id=item.contact_id,
                conversation_id=item.conversation_id,
                agent_id=item.agent_id,
                agent_code=item.agent_code,
                agent_name=agent.name if agent else None,
                user_id=item.user_id,
                org_unit_id=item.org_unit_id,
                org_unit_name=org.name if org else None,
                customer_name=contact.customer_name if contact else None,
                company_name=contact.company_name if contact else None,
                contact_type=contact.contact_type if contact else None,
                contact_value=contact.contact_value if contact else None,
                phone_normalized=contact.phone_normalized if contact else None,
                requirement_summary=item.requirement_summary,
                requirement_types=item.requirement_types or [],
                region=item.region,
                missing_fields=item.missing_fields or [],
                status=item.status,
                has_contact=bool(contact and contact.contact_value),
                event_count=event_counts.get(item.id, 0),
                latest_event=LeadCaptureEventRead.model_validate(latest_event) if latest_event else None,
                created_at=item.created_at,
                updated_at=item.updated_at,
            )
        )
    return result

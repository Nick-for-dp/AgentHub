from datetime import datetime

from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.orm import Session

from app.core.enums import LeadStatus
from app.modules.lead.models import LeadCaptureEvent, LeadContact, SalesLead


class LeadRepository:
    def __init__(self, db: Session):
        self.db = db

    def add_contact(self, contact: LeadContact) -> LeadContact:
        self.db.add(contact)
        self.db.flush()
        return contact

    def save_contact(self, contact: LeadContact) -> LeadContact:
        self.db.add(contact)
        self.db.flush()
        return contact

    def get_contact_by_phone(self, phone_normalized: str) -> LeadContact | None:
        stmt = select(LeadContact).where(LeadContact.phone_normalized == phone_normalized)
        return self.db.scalars(stmt).first()

    def add_sales_lead(self, lead: SalesLead) -> SalesLead:
        self.db.add(lead)
        self.db.flush()
        return lead

    def save_sales_lead(self, lead: SalesLead) -> SalesLead:
        self.db.add(lead)
        self.db.flush()
        return lead

    def get_sales_lead(self, lead_id: str) -> SalesLead | None:
        return self.db.get(SalesLead, lead_id)

    def get_sales_lead_for_context(
        self,
        *,
        lead_id: str,
        conversation_id: str | None,
        user_id: str | None,
        agent_id: str | None,
        org_unit_id: str | None,
    ) -> SalesLead | None:
        stmt = select(SalesLead).where(SalesLead.id == lead_id)
        if conversation_id:
            stmt = stmt.where(SalesLead.conversation_id == conversation_id)
        elif user_id and agent_id:
            stmt = stmt.where(SalesLead.user_id == user_id, SalesLead.agent_id == agent_id)
        else:
            return None

        if user_id:
            stmt = stmt.where(SalesLead.user_id == user_id)
        if agent_id:
            stmt = stmt.where(SalesLead.agent_id == agent_id)
        if org_unit_id:
            stmt = stmt.where(SalesLead.org_unit_id == org_unit_id)
        return self.db.scalars(stmt).first()

    def list_active_leads(
        self,
        *,
        conversation_id: str | None,
        user_id: str | None,
        agent_id: str | None,
    ) -> list[SalesLead]:
        """Return leads that should be visible in known_lead_state.

        Current conversations are the strongest boundary. The user+agent branch
        is kept for non-conversation/API-compatible paths, but normal web chat
        passes a platform conversation_id.
        """
        stmt = select(SalesLead).where(
            SalesLead.status.in_(
                [LeadStatus.PROVISIONAL, LeadStatus.IDENTIFIED, LeadStatus.QUALIFIED]
            )
        )
        if conversation_id:
            stmt = stmt.where(SalesLead.conversation_id == conversation_id)
        elif user_id and agent_id:
            stmt = stmt.where(SalesLead.user_id == user_id, SalesLead.agent_id == agent_id)
        else:
            return []
        stmt = stmt.order_by(SalesLead.updated_at.desc())
        return list(self.db.scalars(stmt))

    def add_capture_event(self, event: LeadCaptureEvent) -> LeadCaptureEvent:
        self.db.add(event)
        self.db.flush()
        return event

    def list_sales_leads(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        agent_code: str | None = None,
        region: str | None = None,
        has_contact: bool | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[SalesLead], int]:
        """Admin-facing lead search across lead facts and contact fields."""
        stmt = select(SalesLead).outerjoin(LeadContact, SalesLead.contact_id == LeadContact.id)

        if keyword:
            pattern = f"%{keyword.strip()}%"
            stmt = stmt.where(
                or_(
                    SalesLead.requirement_summary.ilike(pattern),
                    SalesLead.region.ilike(pattern),
                    SalesLead.agent_code.ilike(pattern),
                    cast(SalesLead.requirement_types, String).ilike(pattern),
                    LeadContact.customer_name.ilike(pattern),
                    LeadContact.company_name.ilike(pattern),
                    LeadContact.contact_value.ilike(pattern),
                    LeadContact.phone_normalized.ilike(pattern),
                )
            )
        if status:
            stmt = stmt.where(SalesLead.status == status)
        if agent_code:
            stmt = stmt.where(SalesLead.agent_code == agent_code)
        if region:
            stmt = stmt.where(SalesLead.region.ilike(f"%{region.strip()}%"))
        if has_contact is True:
            stmt = stmt.where(LeadContact.contact_value.is_not(None), LeadContact.contact_value != "")
        elif has_contact is False:
            stmt = stmt.where(
                or_(
                    SalesLead.contact_id.is_(None),
                    LeadContact.contact_value.is_(None),
                    LeadContact.contact_value == "",
                )
            )
        if created_from:
            stmt = stmt.where(SalesLead.created_at >= created_from)
        if created_to:
            stmt = stmt.where(SalesLead.created_at <= created_to)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = self.db.scalar(count_stmt) or 0

        stmt = stmt.order_by(SalesLead.updated_at.desc(), SalesLead.created_at.desc())
        stmt = stmt.limit(page_size).offset((page - 1) * page_size)
        return list(self.db.scalars(stmt).unique()), total

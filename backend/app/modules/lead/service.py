from typing import Any

from sqlalchemy.orm import Session

from app.core.enums import LeadCaptureEventStatus, LeadStatus
from app.core.security import normalize_phone
from app.modules.agent.models import Agent
from app.modules.agent.output import NormalizedAgentOutput
from app.modules.conversation.models import Conversation
from app.modules.lead.models import LeadCaptureEvent, LeadContact, SalesLead
from app.modules.lead.repository import LeadRepository
from app.modules.lead.schemas import LeadCaptureContext, LeadCaptureResult, LeadDelta


class LeadService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = LeadRepository(db)

    def load_known_lead_state(
        self,
        *,
        conversation: Conversation | None,
        agent: Agent,
        user_id: str | None,
    ) -> dict[str, Any]:
        """Build the lead state passed into Dify before each turn.

        The state is intentionally narrow: it only exposes facts Dify needs for
        attribution and follow-up decisions. AgentHub remains the source of
        truth for lead identity, merge decisions, and database state.
        """
        active_leads = self.repository.list_active_leads(
            conversation_id=conversation.id if conversation else None,
            user_id=user_id,
            agent_id=agent.id,
        )
        return {
            "version": "1.0",
            "conversation_id": conversation.id if conversation else "",
            "active_leads": [self._lead_state_item(lead) for lead in active_leads],
        }

    def capture_output(
        self,
        *,
        output: NormalizedAgentOutput,
        context: LeadCaptureContext,
    ) -> LeadCaptureResult:
        result = LeadCaptureResult()
        for raw_delta in output.lead_deltas:
            event = self._capture_delta(raw_delta=raw_delta, output=output, context=context)
            result.events.append(
                {
                    "event_id": event.id,
                    "status": event.status,
                    "sales_lead_id": event.sales_lead_id,
                    "contact_id": event.contact_id,
                    "reason": event.reason,
                }
            )
            if event.status == LeadCaptureEventStatus.CAPTURED:
                result.captured_count += 1
                if event.sales_lead_id and event.sales_lead_id not in result.lead_ids:
                    result.lead_ids.append(event.sales_lead_id)
                if event.contact_id and event.contact_id not in result.contact_ids:
                    result.contact_ids.append(event.contact_id)
            elif event.status == LeadCaptureEventStatus.FAILED:
                result.failed_count += 1
            else:
                result.ignored_count += 1
        self.db.commit()
        return result

    def _capture_delta(
        self,
        *,
        raw_delta: dict[str, Any],
        output: NormalizedAgentOutput,
        context: LeadCaptureContext,
    ) -> LeadCaptureEvent:
        try:
            delta = LeadDelta.model_validate(raw_delta)
        except Exception as exc:
            return self._create_event(
                context=context,
                raw_delta=raw_delta,
                normalized_delta={},
                followup_decision=output.followup_decision.model_dump(),
                action=None,
                status=LeadCaptureEventStatus.FAILED,
                reason=f"invalid lead delta: {exc}",
            )

        normalized_delta = delta.model_dump()
        if not delta.should_capture or delta.action == "ignore":
            return self._create_event(
                context=context,
                raw_delta=raw_delta,
                normalized_delta=normalized_delta,
                followup_decision=output.followup_decision.model_dump(),
                action=delta.action,
                status=LeadCaptureEventStatus.IGNORED,
                reason=delta.reason or "lead delta marked as not capturable",
            )

        try:
            lead = self._select_target_lead(delta, context)
            contact = self._upsert_contact(delta, context)
            if delta.action == "create_new" or lead is None:
                lead = self._create_sales_lead(delta, context, contact)
            else:
                lead = self._merge_sales_lead(lead, delta, contact)
        except Exception as exc:
            return self._create_event(
                context=context,
                raw_delta=raw_delta,
                normalized_delta=normalized_delta,
                followup_decision=output.followup_decision.model_dump(),
                action=delta.action,
                status=LeadCaptureEventStatus.FAILED,
                reason=f"failed to capture lead delta: {exc}",
            )

        event = self._create_event(
            context=context,
            raw_delta=raw_delta,
            normalized_delta=normalized_delta,
            followup_decision=output.followup_decision.model_dump(),
            action=delta.action,
            status=LeadCaptureEventStatus.CAPTURED,
            reason=delta.reason,
            sales_lead_id=lead.id,
            contact_id=contact.id if contact else None,
        )
        return event

    def _upsert_contact(
        self,
        delta: LeadDelta,
        context: LeadCaptureContext,
    ) -> LeadContact | None:
        phone_normalized: str | None = None
        if delta.contact_type == "phone" and delta.contact_value:
            phone_normalized = normalize_phone(delta.contact_value)

        contact = self.repository.get_contact_by_phone(phone_normalized) if phone_normalized else None
        if contact is None:
            if not any([delta.contact_value, delta.customer_name, delta.company_name]):
                return None
            contact = LeadContact(
                user_id=context.user_id,
                org_unit_id=context.org_unit_id,
                contact_type=delta.contact_type,
                contact_value=delta.contact_value,
                phone_normalized=phone_normalized,
            )
            self.repository.add_contact(contact)

        if delta.customer_name:
            contact.customer_name = delta.customer_name
        if delta.company_name:
            contact.company_name = delta.company_name
        if delta.contact_type:
            contact.contact_type = delta.contact_type
        if delta.contact_value:
            contact.contact_value = delta.contact_value
        if phone_normalized:
            contact.phone_normalized = phone_normalized
        return self.repository.save_contact(contact)

    def _select_target_lead(self, delta: LeadDelta, context: LeadCaptureContext) -> SalesLead | None:
        if delta.target_lead_id:
            lead = self.repository.get_sales_lead_for_context(
                lead_id=delta.target_lead_id,
                conversation_id=context.conversation_id,
                user_id=context.user_id,
                agent_id=context.agent_id,
                org_unit_id=context.org_unit_id,
            )
            if lead is not None:
                return lead
            raise ValueError("target lead does not belong to current capture context")
        active = self.repository.list_active_leads(
            conversation_id=context.conversation_id,
            user_id=context.user_id,
            agent_id=context.agent_id,
        )
        # Conservative fallback: only auto-attach contact-only supplements when
        # there is exactly one active lead. Multi-lead attribution must come
        # from Dify through target_lead_id to avoid merging separate needs.
        if delta.contact_value and len(active) == 1:
            return active[0]
        return None

    def _create_sales_lead(
        self,
        delta: LeadDelta,
        context: LeadCaptureContext,
        contact: LeadContact | None,
    ) -> SalesLead:
        lead = SalesLead(
            contact_id=contact.id if contact else None,
            conversation_id=context.conversation_id,
            agent_id=context.agent_id,
            agent_code=context.agent_code,
            user_id=context.user_id,
            org_unit_id=context.org_unit_id,
            requirement_summary=delta.requirement_summary,
            requirement_types=delta.requirement_types,
            region=delta.region,
            missing_fields=delta.missing_fields,
            status=self._calculate_status(delta.missing_fields),
        )
        return self.repository.add_sales_lead(lead)

    def _merge_sales_lead(
        self,
        lead: SalesLead,
        delta: LeadDelta,
        contact: LeadContact | None,
    ) -> SalesLead:
        if contact is not None:
            lead.contact_id = contact.id
        if delta.requirement_summary:
            lead.requirement_summary = delta.requirement_summary
        if delta.requirement_types:
            lead.requirement_types = delta.requirement_types
        if delta.region:
            lead.region = delta.region
        lead.missing_fields = delta.missing_fields
        lead.status = self._calculate_status(delta.missing_fields)
        return self.repository.save_sales_lead(lead)

    def _create_event(
        self,
        *,
        context: LeadCaptureContext,
        raw_delta: dict[str, Any],
        normalized_delta: dict[str, Any],
        followup_decision: dict[str, Any],
        action: str | None,
        status: str,
        reason: str | None,
        sales_lead_id: str | None = None,
        contact_id: str | None = None,
    ) -> LeadCaptureEvent:
        event = LeadCaptureEvent(
            conversation_id=context.conversation_id,
            conversation_message_id=context.conversation_message_id,
            invocation_record_id=context.invocation_record_id,
            sales_lead_id=sales_lead_id,
            contact_id=contact_id,
            agent_id=context.agent_id,
            agent_code=context.agent_code,
            user_id=context.user_id,
            org_unit_id=context.org_unit_id,
            raw_delta=raw_delta,
            normalized_delta=normalized_delta,
            followup_decision=followup_decision,
            action=action,
            status=status,
            reason=reason,
        )
        return self.repository.add_capture_event(event)

    @staticmethod
    def _calculate_status(missing_fields: list[str]) -> str:
        required_missing = {field for field in missing_fields if field in {"requirement", "region", "contact"}}
        return LeadStatus.QUALIFIED if not required_missing else LeadStatus.PROVISIONAL

    @staticmethod
    def _lead_state_item(lead: SalesLead) -> dict[str, Any]:
        contact = lead.contact
        return {
            "lead_id": lead.id,
            "status": lead.status,
            "requirement_summary": lead.requirement_summary,
            "requirement_types": lead.requirement_types or [],
            "region": lead.region,
            "has_contact": bool(contact and contact.contact_value),
            "missing_fields": lead.missing_fields or [],
        }

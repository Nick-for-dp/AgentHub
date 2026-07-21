from langgraph.runtime import Runtime

from app.core.enums import RiskReviewTargetKind
from app.core.exceptions import ConflictError
from app.modules.risk_assessment.graph.state import RiskGraphContext, RiskGraphState


def apply_human_review(
    state: RiskGraphState,
    runtime: Runtime[RiskGraphContext],
) -> RiskGraphState:
    event = runtime.context.repository.get_review_event(state["review_event_id"])
    if event is None or event.task_id != state["task_id"]:
        raise ConflictError("risk review event does not match task")
    active_item = next(
        (
            item
            for item in state.get("review_items", [])
            if item.get("id") == event.review_item_id and not item.get("is_resolved")
        ),
        None,
    )
    if active_item is None:
        raise ConflictError("risk review item is not active")
    if (
        active_item.get("target_kind") != str(event.target_kind)
        or active_item.get("target_code") != event.target_code
    ):
        raise ConflictError("risk review event target does not match checkpoint")
    facts = {code: dict(fact) for code, fact in state.get("facts", {}).items()}
    documents = [dict(document) for document in state.get("documents", [])]
    affected_fields: list[str] = []
    if event.target_kind == RiskReviewTargetKind.FIELD:
        fact = facts.get(event.target_code)
        if fact is None:
            raise ConflictError("review target field not found")
        value = (event.after_value or {}).get("value")
        status = (
            "ACCEPTED_MISSING" if event.action == "MARK_MISSING" else "ACCEPTED"
        )
        fact.update(
            {
                "value": value,
                "status": status,
                "sources": [
                    *fact.get("sources", []),
                    {"source": "HUMAN_REVIEW", "review_event_id": event.id},
                ],
            }
        )
        affected_fields.append(event.target_code)
    else:
        if event.action != "CONFIRM_DECLARED_TYPE":
            raise ConflictError("document type can only be confirmed in the current task")
        matched = False
        for document in documents:
            if document["id"] == event.target_code:
                matched = True
                document["type_validation_status"] = "MATCHED"
                document["type_validation_warnings"] = []
                for field in document.get("fields", []):
                    if field.pop("type_only_uncertainty", False):
                        field["status"] = "FOUND"
                        affected_fields.append(field["field_code"])
                break
        if not matched:
            raise ConflictError("review target document not found")
        persisted_document = runtime.context.repository.get_document(event.target_code)
        if persisted_document is None or persisted_document.task_id != state["task_id"]:
            raise ConflictError("review target document does not match task")
        persisted_document.type_validation_status = "MATCHED"
        persisted_document.type_validation_warnings = []
        runtime.context.db.add(persisted_document)
    warnings = list(state.get("warnings", []))
    if event.target_kind == RiskReviewTargetKind.FIELD and event.action == "MARK_MISSING":
        warnings.append(f"HUMAN_CONFIRMED_MISSING:{event.target_code}")
    return {
        "facts": facts,
        "documents": documents,
        "affected_fields": list(dict.fromkeys(affected_fields)),
        "review_target_kind": str(event.target_kind),
        "review_signals": [],
        "warnings": list(dict.fromkeys(warnings)),
    }

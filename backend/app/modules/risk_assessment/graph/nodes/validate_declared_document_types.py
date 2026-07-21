from langgraph.runtime import Runtime

from app.modules.risk_assessment.graph.state import RiskGraphContext, RiskGraphState


def validate_declared_document_types(
    state: RiskGraphState,
    runtime: Runtime[RiskGraphContext],
) -> RiskGraphState:
    del runtime
    review_signals: list[dict] = []
    warnings = list(state.get("warnings", []))
    for document in state.get("documents", []):
        status = document.get("type_validation_status")
        if status == "SUSPECTED":
            review_signals.append(
                {
                    "target_kind": "DOCUMENT_TYPE",
                    "target_code": document["id"],
                    "document_id": document["id"],
                    "before": document["document_type"],
                    "alternatives": [],
                    "sources": [],
                    "reason": "DOCUMENT_TYPE_SUSPECTED",
                    "original_filename": document["original_filename"],
                    "declared_document_type": document["document_type"],
                    "warning": "DOCUMENT_TYPE_SUSPECTED",
                }
            )
        elif status == "UNVERIFIED":
            warnings.append(f"DOCUMENT_TYPE_UNVERIFIED:{document['id']}")
    return {"review_signals": review_signals, "warnings": _deduplicate(warnings)}


def _deduplicate(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))

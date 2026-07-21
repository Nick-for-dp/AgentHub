from langgraph.runtime import Runtime

from app.modules.risk_assessment.audit_catalog import AUDIT_FIELDS
from app.modules.risk_assessment.extraction.schemas import ExtractedField
from app.modules.risk_assessment.graph.state import RiskGraphContext, RiskGraphState
from app.modules.risk_assessment.rules.field_resolver import resolve_document_fields
from app.modules.risk_assessment.rules.normalization import normalize_field


def normalize_and_resolve_fields(
    state: RiskGraphState,
    runtime: Runtime[RiskGraphContext],
) -> RiskGraphState:
    del runtime
    documents: list[dict] = []
    for document in state.get("documents", []):
        normalized_fields: list[dict] = []
        for field in document.get("fields", []):
            type_only_uncertainty = bool(field.get("type_only_uncertainty"))
            payload = {key: value for key, value in field.items() if key != "type_only_uncertainty"}
            normalized = normalize_field(ExtractedField.model_validate(payload))
            normalized["type_only_uncertainty"] = type_only_uncertainty
            normalized_fields.append(normalized)
        documents.append(
            {
                **document,
                "fields": normalized_fields,
            }
        )
    facts = resolve_document_fields(documents)
    present_types = {document.get("document_type") for document in documents}
    for definition in AUDIT_FIELDS:
        if definition.code in facts:
            continue
        if not any(document_type.value in present_types for document_type in definition.document_types):
            continue
        facts[definition.code] = {
            "field_code": definition.code,
            "value": None,
            "status": "MISSING",
            "alternatives": [],
            "sources": [],
            "occurrences": [],
        }
    return {"documents": documents, "facts": facts}

from langgraph.runtime import Runtime

from app.modules.risk_assessment.audit_catalog import (
    AUDIT_CATALOG_VERSION,
    AUDIT_FIELDS,
)
from app.modules.risk_assessment.graph.state import (
    RISK_GRAPH_SCHEMA_VERSION,
    RiskGraphContext,
    RiskGraphState,
)
from app.modules.risk_assessment.rules.schemas import RULE_SET_VERSION


def materialize_result_snapshot(
    state: RiskGraphState,
    runtime: Runtime[RiskGraphContext],
) -> RiskGraphState:
    review_targets = {
        (item["target_kind"], item["target_code"])
        for item in state.get("review_items", [])
        if not item.get("is_resolved")
    }
    audit_items: list[dict] = []
    facts = state.get("facts", {})
    for definition in AUDIT_FIELDS:
        fact = facts.get(definition.code)
        if fact is None:
            fact = {
                "field_code": definition.code,
                "value": None,
                "status": "MISSING",
                "alternatives": [],
                "sources": [],
                "occurrences": [],
            }
        occurrences = fact.get("occurrences", [])
        raw_values = _deduplicate(
            [item.get("raw_value") for item in occurrences if item.get("raw_value") is not None]
        )
        normalized_values = _deduplicate(
            [
                item.get("normalized_value")
                for item in occurrences
                if item.get("normalized_value") is not None
            ]
        )
        audit_items.append(
            {
                **fact,
                "label": definition.label,
                "unit": definition.unit,
                "raw_value": raw_values[0] if len(raw_values) == 1 else None,
                "raw_values": raw_values,
                "normalized_value": fact.get("value"),
                "normalized_values": normalized_values,
                "critical": definition.critical,
                "is_review_target": ("FIELD", definition.code) in review_targets,
                "related_checks": [
                    check
                    for check in state.get("checks", [])
                    if definition.code in check.get("affected_fields", [])
                ],
            }
        )
    result = {
        "schema_version": RISK_GRAPH_SCHEMA_VERSION,
        "versions": {
            "audit_catalog": AUDIT_CATALOG_VERSION,
            "rule_set": RULE_SET_VERSION,
            "graph": RISK_GRAPH_SCHEMA_VERSION,
            "documents": [
                {
                    "document_id": document["id"],
                    "parser_version": document["parser_version"],
                    "extractor_version": document["extractor_version"],
                    "provider_version": document["provider_version"],
                }
                for document in state.get("documents", [])
            ],
        },
        "documents": [
            {
                "id": document["id"],
                "file_parse_task_id": document["file_parse_task_id"],
                "original_filename": document["original_filename"],
                "declared_document_type": document["document_type"],
                "type_validation_status": document["type_validation_status"],
                "type_validation_warnings": document["type_validation_warnings"],
            }
            for document in state.get("documents", [])
        ],
        "audit_items": audit_items,
        "document_facts": facts,
        "checks": state.get("checks", []),
        "warnings": state.get("warnings", []),
        "review_items": state.get("review_items", []),
        "overall_status": "NEEDS_REVIEW" if review_targets else "CHECKED",
    }
    task = runtime.context.repository.get_task(state["task_id"])
    if task is not None:
        task.result_snapshot = result
        task.versions = result["versions"]
        runtime.context.db.add(task)
        runtime.context.db.commit()
    return {"result_snapshot": result}


def _deduplicate(values: list) -> list:
    result: list = []
    for value in values:
        if value not in result:
            result.append(value)
    return result

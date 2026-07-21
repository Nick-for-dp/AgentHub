from typing import Any

from app.modules.risk_assessment.audit_catalog import is_critical_field


def partition_unresolved_fields(
    facts: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    review_items: list[dict[str, Any]] = []
    warnings: list[str] = []
    for field_code, fact in facts.items():
        if fact.get("status") not in {"UNRESOLVED", "MISSING"}:
            continue
        if is_critical_field(field_code):
            review_items.append(
                {
                    "target_kind": "FIELD",
                    "target_code": field_code,
                    "alternatives": fact.get("alternatives", []),
                    "sources": fact.get("sources", []),
                    "reason": f"CRITICAL_{fact.get('status')}",
                }
            )
        else:
            warnings.append(f"NON_CRITICAL_{fact.get('status')}:{field_code}")
    return review_items, warnings

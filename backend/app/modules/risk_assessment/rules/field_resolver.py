from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.modules.risk_assessment.extraction.schemas import FieldStatus


def resolve_document_fields(documents: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for document in documents:
        for field in document.get("fields", []):
            occurrence = {
                **field,
                "document_id": document.get("id"),
                "document_type": document.get("document_type"),
                "original_filename": document.get("original_filename"),
                "type_validation_status": document.get("type_validation_status"),
                "type_validation_warnings": document.get("type_validation_warnings", []),
            }
            grouped[field["field_code"]].append(occurrence)

    resolved: dict[str, dict[str, Any]] = {}
    for field_code, occurrences in grouped.items():
        candidates: list[Any] = []
        sources: list[dict[str, Any]] = []
        for item in occurrences:
            if item.get("normalized_value") is not None:
                candidates.append(item["normalized_value"])
            candidates.extend(item.get("alternatives") or [])
            sources.extend(
                {
                    **source,
                    "document_id": item.get("document_id"),
                    "original_filename": item.get("original_filename"),
                    "declared_document_type": item.get("document_type"),
                    "type_validation_status": item.get("type_validation_status"),
                    "type_validation_warnings": item.get("type_validation_warnings", []),
                }
                for source in item.get("sources") or []
            )
        distinct = _deduplicate(candidates)
        statuses = {item.get("status") for item in occurrences}
        if len(distinct) == 1 and FieldStatus.UNCERTAIN.value not in statuses:
            status = "ACCEPTED"
            value = distinct[0]
        elif len(distinct) == 0:
            status = "MISSING"
            value = None
        else:
            status = "UNRESOLVED"
            value = distinct[0] if len(distinct) == 1 else None
        resolved[field_code] = {
            "field_code": field_code,
            "value": value,
            "status": status,
            "alternatives": distinct,
            "sources": sources,
            "occurrences": occurrences,
        }
    return resolved


def _deduplicate(values: list[Any]) -> list[Any]:
    result: list[Any] = []
    for value in values:
        if value not in result:
            result.append(value)
    return result

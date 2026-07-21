from uuid import NAMESPACE_URL, uuid5

from langgraph.runtime import Runtime

from app.modules.risk_assessment.graph.state import RiskGraphContext, RiskGraphState
from app.modules.risk_assessment.rules.criticality import partition_unresolved_fields


def build_review_items(
    state: RiskGraphState,
    runtime: Runtime[RiskGraphContext],
) -> RiskGraphState:
    del runtime
    field_items, field_warnings = partition_unresolved_fields(state.get("facts", {}))
    raw_items = [*state.get("review_signals", []), *field_items]
    items: list[dict] = []
    for item in raw_items:
        target_kind = item["target_kind"]
        target_code = item["target_code"]
        stable_key = f"{state['task_id']}:{target_kind}:{target_code}"
        items.append(
            {
                "id": str(uuid5(NAMESPACE_URL, stable_key)),
                **item,
                "is_resolved": False,
            }
        )
    warnings = list(dict.fromkeys([*state.get("warnings", []), *field_warnings]))
    return {"review_items": items, "warnings": warnings}

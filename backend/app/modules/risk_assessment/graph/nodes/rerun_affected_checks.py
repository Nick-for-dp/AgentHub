from langgraph.runtime import Runtime

from app.core.enums import RiskReviewTargetKind
from app.modules.risk_assessment.graph.nodes.normalize_and_resolve_fields import (
    normalize_and_resolve_fields,
)
from app.modules.risk_assessment.graph.nodes.run_document_checks import run_document_checks
from app.modules.risk_assessment.graph.state import RiskGraphContext, RiskGraphState


def rerun_affected_checks(
    state: RiskGraphState,
    runtime: Runtime[RiskGraphContext],
) -> RiskGraphState:
    """使用 checkpoint 中的字段快照重算，不重新调用 OCR 或字段抽取。"""
    working_state = dict(state)
    if state.get("review_target_kind") == RiskReviewTargetKind.DOCUMENT_TYPE.value:
        working_state.update(normalize_and_resolve_fields(state, runtime))
    checked = run_document_checks(working_state, runtime)
    return {
        **({"documents": working_state["documents"]} if "documents" in working_state else {}),
        **({"facts": working_state["facts"]} if "facts" in working_state else {}),
        **checked,
    }

from langgraph.runtime import Runtime

from app.modules.risk_assessment.graph.state import RiskGraphContext, RiskGraphState


def route_review(
    state: RiskGraphState,
    runtime: Runtime[RiskGraphContext],
) -> RiskGraphState:
    del runtime
    unresolved = [item for item in state.get("review_items", []) if not item.get("is_resolved")]
    return {"execution_state": "WAITING_REVIEW" if unresolved else "READY_TO_FINALIZE"}


def review_route(state: RiskGraphState) -> str:
    return "wait" if state.get("execution_state") == "WAITING_REVIEW" else "finalize"

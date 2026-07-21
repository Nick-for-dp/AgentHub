from langgraph.runtime import Runtime

from app.modules.risk_assessment.graph.state import RiskGraphContext, RiskGraphState


def finalize_document_result(
    state: RiskGraphState,
    runtime: Runtime[RiskGraphContext],
) -> RiskGraphState:
    result = dict(state.get("result_snapshot", {}))
    if any(str(warning).startswith("RULE_FAILED") for warning in result.get("warnings", [])):
        result["overall_status"] = "INCONSISTENT"
    else:
        result["overall_status"] = "CHECKED"
    task = runtime.context.repository.get_task(state["task_id"])
    if task is not None:
        task.result_snapshot = result
        runtime.context.db.add(task)
        runtime.context.db.commit()
    return {"result_snapshot": result, "execution_state": "SUCCEEDED"}

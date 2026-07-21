from langgraph.runtime import Runtime
from langgraph.types import interrupt

from app.modules.risk_assessment.graph.state import RiskGraphContext, RiskGraphState


def interrupt_review(
    state: RiskGraphState,
    runtime: Runtime[RiskGraphContext],
) -> RiskGraphState:
    """触发 LangGraph interrupt；完整复核上下文由 task.result_snapshot 查询。"""
    del runtime
    interrupt(
        {
            "task_id": state["task_id"],
            "thread_id": state["thread_id"],
            "review_item_ids": [item["id"] for item in state.get("review_items", [])],
        }
    )
    return {}

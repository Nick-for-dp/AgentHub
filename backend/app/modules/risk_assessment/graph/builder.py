from __future__ import annotations

from typing import Any, cast

from langgraph.graph import END, START, StateGraph

from app.modules.risk_assessment.graph.nodes import (
    apply_human_review,
    build_review_items,
    extract_documents,
    finalize_document_result,
    interrupt_review,
    load_file_parse_results,
    materialize_result_snapshot,
    normalize_and_resolve_fields,
    rerun_affected_checks,
    route_review,
    run_document_checks,
    validate_declared_document_types,
)
from app.modules.risk_assessment.graph.nodes.route_review import review_route
from app.modules.risk_assessment.graph.state import RiskGraphContext, RiskGraphState


class RiskAssessmentGraph:
    """单张确定性 LangGraph；MySQL checkpoint 由外层 executor 持久化。"""

    def __init__(self) -> None:
        builder = StateGraph(RiskGraphState, context_schema=RiskGraphContext)
        builder.add_node("load_file_parse_results", load_file_parse_results)
        builder.add_node("extract_documents", extract_documents)
        builder.add_node("validate_declared_document_types", validate_declared_document_types)
        builder.add_node("normalize_and_resolve_fields", normalize_and_resolve_fields)
        builder.add_node("run_document_checks", run_document_checks)
        builder.add_node("build_review_items", build_review_items)
        builder.add_node("materialize_result_snapshot", materialize_result_snapshot)
        builder.add_node("route_review", route_review)
        builder.add_node("interrupt_review", interrupt_review)
        builder.add_node("apply_human_review", apply_human_review)
        builder.add_node("rerun_affected_checks", rerun_affected_checks)
        builder.add_node("finalize_document_result", finalize_document_result)
        builder.add_conditional_edges(
            START,
            lambda state: "resume" if state.get("review_event_id") else "start",
            {"start": "load_file_parse_results", "resume": "apply_human_review"},
        )
        builder.add_edge("load_file_parse_results", "extract_documents")
        builder.add_edge("extract_documents", "validate_declared_document_types")
        builder.add_edge("validate_declared_document_types", "normalize_and_resolve_fields")
        builder.add_edge("normalize_and_resolve_fields", "run_document_checks")
        builder.add_edge("run_document_checks", "build_review_items")
        builder.add_edge("build_review_items", "materialize_result_snapshot")
        builder.add_edge("materialize_result_snapshot", "route_review")
        builder.add_conditional_edges(
            "route_review",
            review_route,
            {"wait": "interrupt_review", "finalize": "finalize_document_result"},
        )
        builder.add_edge("interrupt_review", END)
        builder.add_edge("apply_human_review", "rerun_affected_checks")
        builder.add_edge("rerun_affected_checks", "build_review_items")
        builder.add_edge("finalize_document_result", END)
        self.compiled = builder.compile(name="risk-assessment-graph")

    async def invoke(
        self,
        state: RiskGraphState,
        *,
        context: RiskGraphContext,
    ) -> RiskGraphState:
        result: dict[str, Any] = await self.compiled.ainvoke(state, context=context)
        return cast(RiskGraphState, result)

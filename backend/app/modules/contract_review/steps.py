"""合同审查 TaskHandler 的三个领域阶段。

领域细节留在 ``modules/contract_review``：

- 前处理加载解析快照并构造 workflow 输入；
- 核心处理只经 ``AgentRuntimeService.run_workflow``；
- 后处理完成抽取归一化、后端确定性规则判敏、高亮和 result 组装。

规则与高亮属于合同审查主产物，任一步失败都会由 TaskHandler 模板将业务任务和
invocation 标记为 FAILED；这与 chat 线索后处理器的 warning 隔离策略不同。
"""

from __future__ import annotations

from app.core.exceptions import ConflictError
from app.modules.agent.task_handlers import TaskContext
from app.modules.agent.task_handlers.pipeline import (
    CoreResult,
    PostprocessResult,
    PreprocessResult,
)
from app.modules.contract_review.workflow_input import build_contract_review_workflow_input
from app.modules.contract_review.workflow_output import (
    ExtractedClause,
    parse_contract_clause_extraction,
)
from app.modules.contract_review.highlight import HighlightResolver
from app.modules.contract_review.models import ContractReviewTask
from app.modules.contract_review.rules import CreditClauseRuleEngine
from app.modules.contract_review.service import ContractReviewService


class ContractReviewPreprocessStep:
    """就绪校验、解析上下文加载与 workflow 输入组装。"""

    def run(self, ctx: TaskContext) -> PreprocessResult:
        task: ContractReviewTask = ctx.state["task"]
        service: ContractReviewService = ctx.state["contract_review_service"]
        file_parse_task = service.get_ready_file_parse_task(
            task.file_parse_task_id,
            ctx.subject,
        )
        parsed_snapshot = file_parse_task.result_snapshot
        if not isinstance(parsed_snapshot, dict):
            raise ConflictError("file parse task result snapshot is required")

        workflow_input = build_contract_review_workflow_input(
            file_parse_task_id=file_parse_task.id,
            contract_type=task.contract_type,
            parsed_document=parsed_snapshot,
        )
        extras = {
            "schema_version": workflow_input.schema_version,
            "context_chars": len(workflow_input.context_text),
            "parsed_snapshot": parsed_snapshot,
            "file_parse_task_id": file_parse_task.id,
        }
        ctx.state["preprocess_extras"] = extras
        return PreprocessResult(
            workflow_inputs=workflow_input.to_workflow_inputs(),
            extras=extras,
        )


class ContractReviewWorkflowCoreStep:
    """合同审查唯一模型调用点：平台 AgentRuntime workflow 门面。"""

    async def run(self, ctx: TaskContext, pre: PreprocessResult) -> CoreResult:
        subject = ctx.subject
        workflow_result = await ctx.runtime_service.run_workflow(
            ctx.agent,
            inputs=pre.workflow_inputs,
            caller_id=subject.user_id or subject.api_key_id or "contract-review",
        )
        if workflow_result.error or (
            workflow_result.status
            and workflow_result.status.lower() not in {"succeeded", "finished", "success"}
        ):
            raise RuntimeError(workflow_result.error or workflow_result.status or "workflow failed")

        result = CoreResult(
            outputs=workflow_result.outputs or {},
            status=workflow_result.status,
            error=workflow_result.error,
            workflow_run_id=getattr(workflow_result, "workflow_run_id", None),
            total_tokens=getattr(workflow_result, "total_tokens", None),
            elapsed_time=getattr(workflow_result, "elapsed_time", None),
            raw=workflow_result,
        )
        ctx.state["core_result"] = result
        return result


class ContractReviewPostprocessStep:
    """抽取归一化、规则判敏、高亮与最终业务 result 组装。"""

    def __init__(self, rule_engine: CreditClauseRuleEngine | None = None) -> None:
        self.rule_engine = rule_engine or CreditClauseRuleEngine()

    def run(
        self,
        ctx: TaskContext,
        pre: PreprocessResult,
        core: CoreResult,
    ) -> PostprocessResult:
        task: ContractReviewTask = ctx.state["task"]
        extraction = parse_contract_clause_extraction(core.outputs)
        result = self._build_review_result(
            extraction_clauses=extraction.clauses,
            extraction_warnings=extraction.warnings,
            parsed_snapshot=pre.extras["parsed_snapshot"],
            counterparty_level=task.counterparty_level,
        )
        return PostprocessResult(
            business_result=result,
            output_for_invocation=result,
            token_usage={"total_tokens": core.total_tokens},
        )

    def _build_review_result(
        self,
        *,
        extraction_clauses: list[ExtractedClause],
        extraction_warnings: list[dict],
        parsed_snapshot: dict,
        counterparty_level: str,
    ) -> dict:
        highlight_resolver = HighlightResolver(parsed_snapshot)
        clause_results: list[dict] = []
        warning_count = len(extraction_warnings)
        for clause in extraction_clauses:
            judgment = self.rule_engine.judge(
                counterparty_level=counterparty_level,
                clause_category=clause.category,
            )
            highlight = highlight_resolver.resolve(
                clause_text=clause.text,
                source_block_ids=clause.source_block_ids,
            )
            clause_warnings = list(highlight.warnings)
            warning_count += len(clause_warnings)
            first_span = highlight.source_spans[0] if highlight.source_spans else None
            clause_results.append(
                {
                    "text": clause.text,
                    "category": clause.category,
                    "matrix_clause": judgment.matrix_clause,
                    "source": {
                        "section_id": first_span.section_id if first_span else None,
                        "section_title": first_span.section_title if first_span else None,
                        "block_id": first_span.block_id
                        if first_span
                        else (clause.source_block_ids[0] if clause.source_block_ids else None),
                        "text_offset": first_span.start_offset if first_span else None,
                    },
                    "source_block_ids": clause.source_block_ids,
                    "source_spans": [span.to_dict() for span in highlight.source_spans],
                    "is_sensitive": judgment.is_sensitive,
                    "risk_level": judgment.risk_level,
                    "matched_rules": judgment.matched_rules,
                    "reason": judgment.reason,
                    "confidence": clause.confidence,
                    "warnings": clause_warnings,
                }
            )

        sensitive_count = sum(1 for item in clause_results if item["is_sensitive"])
        highest_risk_level = "HIGH" if sensitive_count else ("LOW" if clause_results else None)
        return {
            "clauses": clause_results,
            "summary": {
                "total_clause_count": len(clause_results),
                "sensitive_clause_count": sensitive_count,
                "highest_risk_level": highest_risk_level,
                "warning_count": warning_count,
            },
            "warnings": extraction_warnings,
        }

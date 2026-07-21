from langgraph.runtime import Runtime

from app.modules.risk_assessment.graph.state import RiskGraphContext, RiskGraphState
from app.modules.risk_assessment.rules import (
    run_contract_amount_checks,
    run_payment_ratio_checks,
    run_settlement_checks,
    run_timeline_checks,
)
from app.modules.risk_assessment.rules.schemas import RuleOutcome


def run_document_checks(
    state: RiskGraphState,
    runtime: Runtime[RiskGraphContext],
) -> RiskGraphState:
    del runtime
    facts = {code: dict(fact) for code, fact in state.get("facts", {}).items()}
    results = [
        *run_contract_amount_checks(facts),
        *run_payment_ratio_checks(facts),
        *run_settlement_checks(facts),
        *run_timeline_checks(facts),
    ]
    for result in results:
        if result.outcome == RuleOutcome.RESOLVED and result.selected_value is not None:
            for field_code in result.affected_fields:
                if field_code in facts:
                    facts[field_code]["value"] = result.selected_value
                    facts[field_code]["status"] = "ACCEPTED"
                    facts[field_code]["sources"] = _merge_sources(
                        facts[field_code].get("sources") or [],
                        _derived_sources(result),
                    )
                    facts[field_code]["derivation"] = {
                        "rule_code": result.rule_code,
                        "input_fields": [
                            item.get("field_code")
                            for item in result.input_evidence
                            if item.get("field_code") != field_code
                        ],
                    }
    checks = [result.model_dump(mode="json") for result in results]
    warnings = list(state.get("warnings", []))
    warnings.extend(
        f"RULE_{result.outcome.value}:{result.rule_code}"
        for result in results
        if result.outcome in {RuleOutcome.WARNING, RuleOutcome.FAILED}
    )
    return {"facts": facts, "checks": checks, "warnings": list(dict.fromkeys(warnings))}


def _derived_sources(result) -> list[dict]:
    sources: list[dict] = []
    for item in result.input_evidence:
        for source in item.get("sources") or []:
            derived_source = {
                **source,
                "source": "DERIVED_RULE",
                "rule_code": result.rule_code,
                "input_field_code": item.get("field_code"),
            }
            if derived_source not in sources:
                sources.append(derived_source)
    return sources


def _merge_sources(existing: list[dict], derived: list[dict]) -> list[dict]:
    result = list(existing)
    for source in derived:
        if source not in result:
            result.append(source)
    return result

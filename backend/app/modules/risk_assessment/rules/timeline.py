from datetime import date
from typing import Any

from app.modules.risk_assessment.rules.schemas import RuleOutcome, RuleResult


def run_timeline_checks(facts: dict[str, dict[str, Any]]) -> list[RuleResult]:
    purchase = _date_value(facts, "purchase_signing_date")
    sales = _date_value(facts, "sales_signing_date")
    evidence = [
        {"field_code": code, **(facts.get(code) or {})}
        for code in ("purchase_signing_date", "sales_signing_date")
    ]
    if purchase is None or sales is None:
        return [RuleResult(rule_code="CONTRACT_SIGNING_TIMELINE", outcome=RuleOutcome.NOT_APPLICABLE, input_evidence=evidence, message="合同签订日期不完整", affected_fields=["purchase_signing_date", "sales_signing_date"])]
    outcome = RuleOutcome.PASSED if purchase <= sales else RuleOutcome.WARNING
    return [RuleResult(rule_code="CONTRACT_SIGNING_TIMELINE", outcome=outcome, input_evidence=evidence, message="采购签订日不晚于销售签订日" if outcome == RuleOutcome.PASSED else "采购签订日晚于销售签订日", affected_fields=["purchase_signing_date", "sales_signing_date"])]


def _date_value(facts: dict[str, dict[str, Any]], code: str) -> date | None:
    value = (facts.get(code) or {}).get("value")
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None

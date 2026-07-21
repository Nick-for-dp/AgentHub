from decimal import Decimal
from typing import Any

from app.modules.risk_assessment.rules.normalization import to_decimal
from app.modules.risk_assessment.rules.schemas import RuleOutcome, RuleResult


def run_settlement_checks(facts: dict[str, dict[str, Any]]) -> list[RuleResult]:
    quantity = to_decimal((facts.get("settlement_quantity") or {}).get("value"))
    unit_price = to_decimal((facts.get("sales_unit_price_tax_included") or {}).get("value"))
    amount = to_decimal((facts.get("settlement_amount") or {}).get("value"))
    evidence = [
        {"field_code": code, **(facts.get(code) or {})}
        for code in ("settlement_quantity", "sales_unit_price_tax_included", "settlement_amount")
    ]
    if quantity is None or unit_price is None or amount is None:
        return [RuleResult(rule_code="SETTLEMENT_AMOUNT_FORMULA", outcome=RuleOutcome.NOT_APPLICABLE, input_evidence=evidence, message="结算公式输入不完整", affected_fields=["settlement_quantity", "sales_unit_price_tax_included", "settlement_amount"])]
    delta = abs(quantity * unit_price - amount)
    outcome = RuleOutcome.PASSED if delta <= Decimal("0.01") else RuleOutcome.WARNING
    return [RuleResult(rule_code="SETTLEMENT_AMOUNT_FORMULA", outcome=outcome, input_evidence=evidence, message="结算数量×销售单价与结算金额一致" if outcome == RuleOutcome.PASSED else "结算金额包含未配置口径的差异", affected_fields=["settlement_amount"])]

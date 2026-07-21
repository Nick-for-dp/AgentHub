from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from app.modules.risk_assessment.rules.normalization import to_decimal
from app.modules.risk_assessment.rules.schemas import RuleOutcome, RuleResult


def run_payment_ratio_checks(facts: dict[str, dict[str, Any]]) -> list[RuleResult]:
    amount = to_decimal((facts.get("purchase_amount_tax_included") or {}).get("value"))
    ratio = to_decimal((facts.get("deposit_ratio") or {}).get("value"))
    deposit = to_decimal((facts.get("deposit_amount") or {}).get("value"))
    evidence = [
        {"field_code": code, **(facts.get(code) or {})}
        for code in ("purchase_amount_tax_included", "deposit_ratio", "deposit_amount")
    ]
    if amount is None or ratio is None:
        return [RuleResult(rule_code="DEPOSIT_RATIO_AMOUNT", outcome=RuleOutcome.NOT_APPLICABLE, input_evidence=evidence, message="采购合同含税金额或保证金比例缺失，无法计算保证金金额", affected_fields=["deposit_amount"])]
    expected = (amount * ratio / Decimal("100")).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )
    if deposit is None:
        return [
            RuleResult(
                rule_code="DEPOSIT_RATIO_AMOUNT",
                outcome=RuleOutcome.RESOLVED,
                input_evidence=evidence,
                message="按采购合同含税金额×保证金比例计算保证金金额",
                affected_fields=["deposit_amount"],
                selected_value=_decimal_text(expected),
            )
        ]
    outcome = RuleOutcome.PASSED if abs(expected - deposit) <= Decimal("0.01") else RuleOutcome.FAILED
    return [RuleResult(rule_code="DEPOSIT_RATIO_AMOUNT", outcome=outcome, input_evidence=evidence, message="保证金比例与金额一致" if outcome == RuleOutcome.PASSED else "保证金比例与金额不一致", affected_fields=["deposit_ratio", "deposit_amount"])]


def _decimal_text(value: Decimal) -> str:
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text

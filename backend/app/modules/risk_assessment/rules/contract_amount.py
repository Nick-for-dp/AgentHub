from decimal import Decimal
from typing import Any

from app.modules.risk_assessment.rules.normalization import to_decimal
from app.modules.risk_assessment.rules.schemas import RuleOutcome, RuleResult


AMOUNT_TOLERANCE = Decimal("0.01")


def run_contract_amount_checks(facts: dict[str, dict[str, Any]]) -> list[RuleResult]:
    return [
        _check("PURCHASE_AMOUNT_FORMULA", "purchase_quantity", "purchase_unit_price_tax_included", "purchase_amount_tax_included", facts),
        _check("SALES_AMOUNT_FORMULA", "sales_quantity", "sales_unit_price_tax_included", "sales_amount_tax_included", facts),
    ]


def _check(rule_code: str, quantity_code: str, price_code: str, amount_code: str, facts: dict[str, dict[str, Any]]) -> RuleResult:
    quantity = _fact_decimal(facts, quantity_code)
    amount = _fact_decimal(facts, amount_code)
    price_fact = facts.get(price_code) or {}
    candidates = _candidate_decimals(price_fact)
    evidence = [_evidence(facts, code) for code in (quantity_code, price_code, amount_code)]
    if quantity is None or amount is None or not candidates:
        return RuleResult(rule_code=rule_code, outcome=RuleOutcome.NOT_APPLICABLE, input_evidence=evidence, message="公式输入不完整", affected_fields=[quantity_code, price_code, amount_code])
    matches = [value for value in candidates if abs(quantity * value - amount) <= AMOUNT_TOLERANCE]
    if len(matches) == 1:
        selected = format(matches[0], "f")
        outcome = RuleOutcome.RESOLVED if len(candidates) > 1 else RuleOutcome.PASSED
        return RuleResult(rule_code=rule_code, outcome=outcome, input_evidence=evidence, message="数量×单价与金额一致", affected_fields=[price_code], selected_value=selected)
    return RuleResult(rule_code=rule_code, outcome=RuleOutcome.FAILED, input_evidence=evidence, message="数量×单价与金额不一致", affected_fields=[quantity_code, price_code, amount_code])


def _fact_decimal(facts: dict[str, dict[str, Any]], code: str) -> Decimal | None:
    return to_decimal((facts.get(code) or {}).get("value"))


def _candidate_decimals(fact: dict[str, Any]) -> list[Decimal]:
    values = [fact.get("value"), *(fact.get("alternatives") or [])]
    result: list[Decimal] = []
    for value in values:
        parsed = to_decimal(value)
        if parsed is not None and parsed not in result:
            result.append(parsed)
    return result


def _evidence(facts: dict[str, dict[str, Any]], code: str) -> dict[str, Any]:
    fact = facts.get(code) or {}
    return {"field_code": code, "value": fact.get("value"), "alternatives": fact.get("alternatives", []), "sources": fact.get("sources", [])}

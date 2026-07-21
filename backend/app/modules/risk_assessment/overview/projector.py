from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from app.modules.risk_assessment.overview.catalog import BUSINESS_OVERVIEW_DEFINITIONS
from app.modules.risk_assessment.overview.schemas import (
    BusinessOverviewDisplayStatus,
    BusinessOverviewProjection,
    BusinessOverviewRow,
)


class BusinessOverviewProjector:
    """把 canonical 风控结果投影为 Web/Excel 共用的 17 项业务总览。"""

    def project(
        self,
        *,
        business_code: str,
        generated_at: datetime,
        result: dict[str, Any] | None,
        review_events: list[Any] | None = None,
    ) -> BusinessOverviewProjection | None:
        if not result:
            return None
        facts = result.get("document_facts") or {}
        audit_items = {
            item.get("field_code"): item for item in result.get("audit_items", [])
        }
        reviewed_codes = {
            _event_value(event, "target_code")
            for event in review_events or []
            if _event_value(event, "target_code")
        }
        rows: list[BusinessOverviewRow] = []
        for definition in BUSINESS_OVERVIEW_DEFINITIONS:
            if definition.formatter == "contract_quantity":
                row = self._contract_quantity_row(definition, facts, audit_items)
            elif definition.formatter == "deposit":
                row = self._deposit_row(definition, facts, audit_items)
            elif definition.formatter == "floating_fee":
                row = self._floating_fee_row(definition, facts, audit_items)
            else:
                row = self._direct_row(definition, facts, audit_items)
            if reviewed_codes.intersection(definition.field_codes):
                row = row.model_copy(update={"is_human_reviewed": True})
            rows.append(row)
        return BusinessOverviewProjection(
            business_code=business_code,
            generated_at=generated_at,
            rows=rows,
        )

    def _direct_row(self, definition, facts, audit_items) -> BusinessOverviewRow:
        field_code = definition.field_codes[0]
        fact = _resolved_fact(field_code, facts, audit_items)
        status = _display_status([fact], audit_items)
        content = _direct_content(field_code, fact, status)
        return _row(definition, content, status, [fact])

    def _contract_quantity_row(self, definition, facts, audit_items) -> BusinessOverviewRow:
        purchase = _resolved_fact("purchase_quantity", facts, audit_items)
        sales = _resolved_fact("sales_quantity", facts, audit_items)
        status = _display_status([purchase, sales], audit_items, composite=True)
        purchase_value = _usable_value(purchase)
        sales_value = _usable_value(sales)
        if purchase_value is None and sales_value is None:
            content = _missing_content([purchase, sales])
        elif purchase_value is not None and sales_value is not None:
            purchase_text = _format_value("purchase_quantity", purchase_value)
            sales_text = _format_value("sales_quantity", sales_value)
            if _values_equal(purchase_value, sales_value):
                content = purchase_text
            else:
                content = f"采购约定：{purchase_text}；销售约定：{sales_text}"
        else:
            purchase_text = (
                _format_value("purchase_quantity", purchase_value)
                if purchase_value is not None
                else "未识别"
            )
            sales_text = (
                _format_value("sales_quantity", sales_value)
                if sales_value is not None
                else "未识别"
            )
            content = f"采购约定：{purchase_text}；销售约定：{sales_text}"
        return _row(definition, content, status, [purchase, sales])

    def _deposit_row(self, definition, facts, audit_items) -> BusinessOverviewRow:
        ratio = _resolved_fact("deposit_ratio", facts, audit_items)
        amount = _resolved_fact("deposit_amount", facts, audit_items)
        status = _display_status([ratio, amount], audit_items, composite=True)
        ratio_value = _usable_value(ratio)
        amount_value = _usable_value(amount)
        if ratio_value is None and amount_value is None:
            content = _missing_content([ratio, amount])
        elif ratio_value is not None and amount_value is not None:
            content = (
                f"{_format_value('deposit_ratio', ratio_value)}"
                f"（{_format_deposit_amount(amount_value)}）"
            )
        elif ratio_value is not None:
            content = f"{_format_value('deposit_ratio', ratio_value)}（金额未明示）"
        else:
            content = f"比例未识别（{_format_value('deposit_amount', amount_value)}）"
        return _row(definition, content, status, [ratio, amount])

    def _floating_fee_row(self, definition, facts, audit_items) -> BusinessOverviewRow:
        fee = _resolved_fact("floating_fee", facts, audit_items)
        days = _resolved_fact("occupied_days", facts, audit_items)
        status = _display_status([fee, days], audit_items, composite=True)
        fee_value = _usable_value(fee)
        days_value = _usable_value(days)
        if fee_value is None and days_value is None:
            content = _missing_content([fee, days])
        elif fee_value is not None and days_value is not None:
            content = (
                f"{_format_value('floating_fee', fee_value)}"
                f"（{_format_value('occupied_days', days_value)}）"
            )
        elif fee_value is not None:
            content = f"{_format_value('floating_fee', fee_value)}（占用天数未识别）"
        else:
            content = f"费用未识别（{_format_value('occupied_days', days_value)}）"
        return _row(definition, content, status, [fee, days])


def _row(definition, content: str, status, facts: list[dict[str, Any]]) -> BusinessOverviewRow:
    return BusinessOverviewRow(
        code=definition.code,
        label=definition.label,
        content=content,
        status=status,
        source_files=_source_files(facts),
        field_codes=list(definition.field_codes),
        is_human_reviewed=any(_is_human_fact(fact) for fact in facts),
    )


def _resolved_fact(
    field_code: str,
    facts: dict[str, dict[str, Any]],
    audit_items: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    return facts.get(field_code) or audit_items.get(field_code) or {
        "field_code": field_code,
        "value": None,
        "status": "MISSING",
        "alternatives": [],
        "sources": [],
        "occurrences": [],
    }


def _display_status(
    facts: list[dict[str, Any]],
    audit_items: dict[str, dict[str, Any]],
    *,
    composite: bool = False,
) -> BusinessOverviewDisplayStatus:
    field_codes = [fact.get("field_code") for fact in facts if fact.get("field_code")]
    if any((audit_items.get(code) or {}).get("is_review_target") for code in field_codes):
        return BusinessOverviewDisplayStatus.NEEDS_REVIEW
    if any(fact.get("status") == "UNRESOLVED" for fact in facts):
        return BusinessOverviewDisplayStatus.NEEDS_REVIEW
    present = sum(_usable_value(fact) is not None for fact in facts)
    if present == 0:
        return BusinessOverviewDisplayStatus.MISSING
    if composite and present < len(facts):
        return BusinessOverviewDisplayStatus.PARTIAL
    return BusinessOverviewDisplayStatus.READY


def _direct_content(
    field_code: str,
    fact: dict[str, Any],
    status: BusinessOverviewDisplayStatus,
) -> str:
    value = _usable_value(fact)
    if value is not None:
        return _format_value(field_code, value)
    if fact.get("status") == "ACCEPTED_MISSING":
        return "人工确认缺失"
    if status == BusinessOverviewDisplayStatus.NEEDS_REVIEW:
        alternatives = fact.get("alternatives") or []
        if alternatives:
            return "待复核：" + "；".join(_format_value(field_code, item) for item in alternatives)
        return "待复核"
    return "未识别"


def _missing_content(facts: list[dict[str, Any]]) -> str:
    return "人工确认缺失" if any(
        fact.get("status") == "ACCEPTED_MISSING" for fact in facts
    ) else "未识别"


def _usable_value(fact: dict[str, Any]) -> Any | None:
    if fact.get("status") in {"MISSING", "ACCEPTED_MISSING"}:
        return None
    return fact.get("value")


def _format_value(field_code: str, value: Any) -> str:
    if value is None:
        return "未识别"
    if "date" in field_code:
        text = str(value)
        try:
            year, month, day = (int(part) for part in text[:10].split("-"))
            return f"{year}年{month}月{day}日"
        except (TypeError, ValueError):
            return text
    if field_code in {"purchase_quantity", "sales_quantity"}:
        return f"{_number_text(value, 3)} 吨"
    if "unit_price" in field_code:
        return f"{_number_text(value, 2, fixed=True)} 元/吨"
    if field_code == "deposit_ratio":
        return f"{_number_text(value, 2)}%"
    if field_code == "occupied_days":
        return f"{_number_text(value, 0)}天"
    if field_code in {
        "purchase_amount_tax_included",
        "sales_amount_tax_included",
        "key_customer_discount",
        "deposit_amount",
        "floating_fee",
    }:
        return f"{_number_text(value, 2, fixed=True)} 元"
    return str(value)


def _number_text(value: Any, precision: int, *, fixed: bool = False) -> str:
    try:
        number = Decimal(str(value).replace(",", ""))
    except (InvalidOperation, ValueError):
        return str(value)
    formatted = f"{number:,.{precision}f}"
    if not fixed and "." in formatted:
        formatted = formatted.rstrip("0").rstrip(".")
    return formatted


def _format_deposit_amount(value: Any) -> str:
    return f"{_number_text(value, 2)}元"


def _values_equal(left: Any, right: Any) -> bool:
    try:
        return Decimal(str(left).replace(",", "")) == Decimal(str(right).replace(",", ""))
    except InvalidOperation:
        return str(left).strip() == str(right).strip()


def _source_files(facts: list[dict[str, Any]]) -> list[str]:
    result: list[str] = []
    for fact in facts:
        candidates = [
            source.get("original_filename")
            for source in fact.get("sources") or []
            if source.get("original_filename")
        ]
        candidates.extend(
            item.get("original_filename")
            for item in fact.get("occurrences") or []
            if item.get("original_filename")
        )
        for filename in candidates:
            if filename not in result:
                result.append(filename)
    return result


def _is_human_fact(fact: dict[str, Any]) -> bool:
    return any(source.get("source") == "HUMAN_REVIEW" for source in fact.get("sources") or [])


def _event_value(event: Any, field: str) -> Any:
    return event.get(field) if isinstance(event, dict) else getattr(event, field, None)

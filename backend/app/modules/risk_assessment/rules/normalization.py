from __future__ import annotations

import re
import unicodedata
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from app.modules.risk_assessment.extraction.schemas import ExtractedField, FieldStatus


PLACEHOLDERS = {"", "-", "—", "/", "无", "不适用", "n/a", "none"}
NUMERIC_MARKERS = ("quantity", "price", "amount", "ratio", "fee", "days", "payment")


def normalize_field(field: ExtractedField) -> dict[str, Any]:
    raw_value = field.raw_value
    if _is_placeholder(raw_value):
        return {
            **field.model_dump(mode="json"),
            "raw_value": None,
            "normalized_value": None,
            "status": FieldStatus.MISSING.value,
            "alternatives": [],
        }
    normalized = normalize_value(field.field_code, field.normalized_value or raw_value)
    unit = field.unit or infer_unit(field.field_code)
    return {
        **field.model_dump(mode="json"),
        "normalized_value": normalized,
        "unit": unit,
    }


def normalize_value(field_code: str, value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return str(value) if any(marker in field_code for marker in NUMERIC_MARKERS) else value
    if field_code == "raw_business_mode_text":
        # 业务模式在本阶段是审批样表原文，不做 NFKC、枚举化或别名改写。
        return str(value).strip()
    text = unicodedata.normalize("NFKC", str(value)).strip()
    text = " ".join(text.split())
    if "date" in field_code:
        parsed = _parse_date(text)
        return parsed.isoformat() if parsed else text
    if any(marker in field_code for marker in NUMERIC_MARKERS):
        numeric = _parse_decimal(text)
        return _decimal_text(numeric) if numeric is not None else text
    if field_code in {"upstream_supplier", "downstream_customer", "upstream_supplier_raw", "downstream_customer_raw"}:
        return re.sub(r"\s+", "", text)
    return text


def infer_unit(field_code: str) -> str | None:
    if "quantity" in field_code:
        return "TON"
    if "unit_price" in field_code:
        return "CNY/TON"
    if "ratio" in field_code:
        return "PERCENT"
    if "days" in field_code:
        return "DAY"
    if field_code == "key_customer_discount" or any(
        marker in field_code for marker in ("amount", "fee", "payment")
    ):
        return "CNY"
    if "date" in field_code:
        return "DATE"
    return None


def to_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    return _parse_decimal(str(value))


def _is_placeholder(value: Any) -> bool:
    return isinstance(value, str) and unicodedata.normalize("NFKC", value).strip().lower() in PLACEHOLDERS


def _parse_decimal(value: str) -> Decimal | None:
    match = re.search(r"-?\d[\d,]*(?:\.\d+)?", value)
    if not match:
        return None
    try:
        return Decimal(match.group(0).replace(",", ""))
    except InvalidOperation:
        return None


def _decimal_text(value: Decimal) -> str:
    normalized = format(value.normalize(), "f")
    return normalized.rstrip("0").rstrip(".") if "." in normalized else normalized


def _parse_date(value: str) -> date | None:
    match = re.search(r"(20\d{2})[年./-](\d{1,2})[月./-](\d{1,2})日?", value)
    if not match:
        return None
    try:
        return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except ValueError:
        return None

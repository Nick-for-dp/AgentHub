"""合同审查 workflow 输出的领域归一化边界。"""

import json
import re
from dataclasses import dataclass, field
from typing import Any

CLAUSE_EXTRACTION_SCHEMA_VERSION = "contract_clause_extraction_batch_v1"

_CODE_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL | re.IGNORECASE)


@dataclass(frozen=True)
class ExtractedClause:
    """模型 workflow 抽取出的候选条款。

    workflow 只负责 ``text``、``category``、来源 block 和置信度；敏感性结论由
    后端规则引擎生成。
    """

    text: str
    category: str
    source_block_ids: list[str] = field(default_factory=list)
    confidence: float = 0.0
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ContractClauseExtraction:
    """合同条款抽取批次结果。"""

    schema_version: str | None
    clauses: list[ExtractedClause]
    warnings: list[dict[str, Any]]
    raw: Any = None


def parse_contract_clause_extraction(outputs: Any) -> ContractClauseExtraction:
    """从 runtime workflow outputs 中归一化候选条款和 warning。"""
    payload = _find_clause_payload(outputs)
    if isinstance(payload, list):
        return ContractClauseExtraction(
            schema_version=None,
            clauses=_normalize_clauses(payload),
            warnings=[],
            raw=outputs,
        )
    if not isinstance(payload, dict):
        return ContractClauseExtraction(schema_version=None, clauses=[], warnings=[], raw=outputs)

    raw_clauses = payload.get("clauses")
    if raw_clauses is None:
        raw_clauses = payload.get("items") or payload.get("results") or []
    raw_warnings = payload.get("warnings") or payload.get("warning") or []
    return ContractClauseExtraction(
        schema_version=_optional_string(payload.get("schema_version")),
        clauses=_normalize_clauses(raw_clauses),
        warnings=_normalize_warnings(raw_warnings),
        raw=payload,
    )


def _find_clause_payload(value: Any, *, depth: int = 0) -> Any:
    """递归寻找包含 clauses/warnings/schema_version 的对象。"""
    if depth > 8:
        return None
    parsed = _parse_possible_json(value)
    if isinstance(parsed, list):
        return parsed
    if not isinstance(parsed, dict):
        return None
    if any(key in parsed for key in ("clauses", "warnings", "schema_version")):
        return parsed
    for key in ("result", "text", "answer", "output", "outputs", "data"):
        if key in parsed:
            found = _find_clause_payload(parsed[key], depth=depth + 1)
            if found is not None:
                return found
    if len(parsed) == 1:
        return _find_clause_payload(next(iter(parsed.values())), depth=depth + 1)
    return None


def _parse_possible_json(value: Any) -> Any:
    """兼容常见 JSON 字符串和 Markdown code fence。"""
    if not isinstance(value, str):
        return value
    stripped = value.strip()
    if not stripped:
        return value
    match = _CODE_FENCE_RE.match(stripped)
    if match:
        stripped = match.group(1).strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        return value


def _normalize_clauses(raw_clauses: Any) -> list[ExtractedClause]:
    """标准化 clauses 列表。"""
    if not isinstance(raw_clauses, list):
        return []
    clauses: list[ExtractedClause] = []
    for item in raw_clauses:
        if isinstance(item, str):
            text = item.strip()
            if text:
                clauses.append(ExtractedClause(text=text, category="unknown", raw={"text": text}))
            continue
        if not isinstance(item, dict):
            continue
        text = _first_text(
            item,
            "text",
            "clause_text",
            "content",
            "original_text",
            "matched_text",
        )
        if not text:
            continue
        clauses.append(
            ExtractedClause(
                text=text,
                category=_first_text(item, "category", "clause_type", "type") or "unknown",
                source_block_ids=_extract_source_block_ids(item),
                confidence=_optional_float(item.get("confidence")) or 0.0,
                raw=item,
            )
        )
    return clauses


def _normalize_warnings(raw_warnings: Any) -> list[dict[str, Any]]:
    """标准化 workflow warnings。"""
    if raw_warnings is None:
        return []
    items = raw_warnings if isinstance(raw_warnings, list) else [raw_warnings]
    warnings: list[dict[str, Any]] = []
    for item in items:
        if isinstance(item, str):
            text = item.strip()
            if text:
                warnings.append({"message": text})
            continue
        if isinstance(item, dict):
            warnings.append({key: value for key, value in item.items() if value is not None})
    return warnings


def _extract_source_block_ids(item: dict[str, Any]) -> list[str]:
    """从条款 item 中提取 source block ID。"""
    candidates: list[Any] = [
        item.get("source_block_ids"),
        item.get("source_blocks"),
        item.get("block_ids"),
        item.get("block_id"),
        item.get("source_block_id"),
    ]
    source = item.get("source")
    if isinstance(source, dict):
        candidates.extend(
            [
                source.get("source_block_ids"),
                source.get("block_ids"),
                source.get("block_id"),
                source.get("source_block_id"),
            ]
        )
    block_ids: list[str] = []
    for candidate in candidates:
        for block_id in _coerce_string_list(candidate):
            if block_id not in block_ids:
                block_ids.append(block_id)
    return block_ids


def _coerce_string_list(value: Any) -> list[str]:
    """把字符串或列表值统一成字符串列表。"""
    if value is None:
        return []
    if isinstance(value, str):
        normalized = value.strip()
        return [normalized] if normalized else []
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            if isinstance(item, dict):
                text = _first_text(item, "block_id", "source_block_id", "id")
            else:
                text = str(item).strip() if item is not None else None
            if text:
                result.append(text)
        return result
    return []


def _first_text(data: dict[str, Any], *keys: str) -> str | None:
    """按候选字段读取第一个非空字符串。"""
    for key in keys:
        value = data.get(key)
        text = _optional_string(value)
        if text:
            return text
    return None


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

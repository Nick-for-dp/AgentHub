import json
import re
from typing import Any

from pydantic import BaseModel, Field


class NormalizedFollowupDecision(BaseModel):
    should_ask_followup: bool = False
    next_missing_field: str | None = None
    target_lead_id: str | None = None
    followup_goal: str | None = None
    followup_hint: str | None = None
    reason: str = ""


class NormalizedDifyOutput(BaseModel):
    text: str
    lead_deltas: list[dict[str, Any]] = Field(default_factory=list)
    followup_decision: NormalizedFollowupDecision = Field(default_factory=NormalizedFollowupDecision)
    raw: Any = None
    parsed: bool = True

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "lead_deltas": self.lead_deltas,
            "followup_decision": self.followup_decision.model_dump(),
        }


_CODE_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL | re.IGNORECASE)


def normalize_dify_final_output(raw_output: Any) -> NormalizedDifyOutput:
    """Normalize Dify workflow final output into AgentHub's lead-aware contract.

    Dify's answer node may return a mapping directly, a JSON string, or a JSON
    string nested inside "text"/"answer". This function accepts all three forms
    so the rest of AgentHub can consume one stable structure.
    """
    parsed = _parse_possible_json(raw_output)
    if isinstance(parsed, dict):
        return _normalize_from_mapping(parsed, raw_output)

    fallback_text = _fallback_text(raw_output)
    return NormalizedDifyOutput(
        text=fallback_text,
        lead_deltas=[],
        followup_decision=NormalizedFollowupDecision(
            should_ask_followup=False,
            reason="Dify output is not structured lead result; treated as normal reply.",
        ),
        raw=raw_output,
        parsed=False,
    )


def _normalize_from_mapping(data: dict[str, Any], raw_output: Any) -> NormalizedDifyOutput:
    nested = data
    for candidate_key in ("text", "answer"):
        candidate_value = nested.get(candidate_key)
        if isinstance(candidate_value, str):
            parsed_candidate = _parse_possible_json(candidate_value)
            if isinstance(parsed_candidate, dict) and (
                "text" in parsed_candidate
                or "lead_deltas" in parsed_candidate
                or "followup_decision" in parsed_candidate
            ):
                nested = {**nested, **parsed_candidate}
                break

    text_value = nested.get("text")

    text = str(text_value).strip() if text_value is not None else _fallback_text(raw_output)
    lead_deltas = nested.get("lead_deltas")
    if not isinstance(lead_deltas, list):
        lead_deltas = []
    lead_deltas = [item for item in lead_deltas if isinstance(item, dict)]

    followup = nested.get("followup_decision")
    if not isinstance(followup, dict):
        followup = {}

    return NormalizedDifyOutput(
        text=text,
        lead_deltas=lead_deltas,
        followup_decision=NormalizedFollowupDecision(
            should_ask_followup=_coerce_bool(followup.get("should_ask_followup")),
            next_missing_field=_coerce_optional_str(followup.get("next_missing_field")),
            target_lead_id=_coerce_optional_str(followup.get("target_lead_id")),
            followup_goal=_coerce_optional_str(followup.get("followup_goal")),
            followup_hint=_coerce_optional_str(followup.get("followup_hint")),
            reason=str(followup.get("reason") or ""),
        ),
        raw=raw_output,
        parsed=True,
    )


def _parse_possible_json(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    stripped = _strip_code_fence(value.strip())
    if not stripped:
        return value
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        return value


def _strip_code_fence(value: str) -> str:
    match = _CODE_FENCE_RE.match(value)
    if not match:
        return value
    return match.group(1).strip()


def _fallback_text(raw_output: Any) -> str:
    if isinstance(raw_output, str):
        return _strip_code_fence(raw_output.strip())
    if isinstance(raw_output, dict):
        for key in ("text", "answer"):
            value = raw_output.get(key)
            if value is not None:
                return str(value).strip()
    return "" if raw_output is None else str(raw_output)


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y"}
    return bool(value)


def _coerce_optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None

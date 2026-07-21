from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TypedDict

from sqlalchemy.orm import Session

from app.integrations.langgraph_checkpoint.mysql import MySQLRiskCheckpointStore
from app.modules.risk_assessment.extraction.service import DocumentExtractionService
from app.modules.risk_assessment.repository import RiskAssessmentRepository


RISK_GRAPH_SCHEMA_VERSION = "risk-graph-v1"


class RiskGraphState(TypedDict, total=False):
    task_id: str
    thread_id: str
    checkpoint_version: int
    document_ids: list[str]
    documents: list[dict[str, Any]]
    facts: dict[str, dict[str, Any]]
    checks: list[dict[str, Any]]
    warnings: list[str]
    review_signals: list[dict[str, Any]]
    review_items: list[dict[str, Any]]
    review_event_id: str
    review_target_kind: str
    affected_fields: list[str]
    result_snapshot: dict[str, Any]
    execution_state: str


@dataclass
class RiskGraphContext:
    db: Session
    repository: RiskAssessmentRepository
    extraction_service: DocumentExtractionService | None
    checkpoint_store: MySQLRiskCheckpointStore

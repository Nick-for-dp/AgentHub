from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
import re
from urllib.parse import quote

from sqlalchemy.orm import Session

from app.core.enums import RiskAssessmentTaskStatus
from app.core.exceptions import BadRequestError, ConflictError
from app.modules.auth.schemas import AuthenticatedSubject
from app.modules.risk_assessment.export.layout import TEMPLATE_VERSION
from app.modules.risk_assessment.export.writer import RiskAuditWorkbookWriter
from app.modules.risk_assessment.overview import BusinessOverviewProjector
from app.modules.risk_assessment.service import RiskAssessmentService


EXCEL_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_UNSAFE_FILENAME = re.compile(r'[\\/:*?"<>|\x00-\x1f]+')


@dataclass(frozen=True)
class ExportedRiskWorkbook:
    content: BytesIO
    content_type: str
    content_disposition: str


class RiskAuditWorkbookExportService:
    def __init__(
        self,
        db: Session,
        *,
        projector: BusinessOverviewProjector | None = None,
        writer: RiskAuditWorkbookWriter | None = None,
    ) -> None:
        self.risk_service = RiskAssessmentService(db)
        self.projector = projector or BusinessOverviewProjector()
        self.writer = writer or RiskAuditWorkbookWriter()

    def export(
        self,
        *,
        task_id: str,
        subject: AuthenticatedSubject,
        template_version: str = TEMPLATE_VERSION,
    ) -> ExportedRiskWorkbook:
        if template_version != TEMPLATE_VERSION:
            raise BadRequestError("unsupported risk workbook template version")
        task = self.risk_service.get_task(task_id=task_id, subject=subject)
        if task.status != RiskAssessmentTaskStatus.SUCCEEDED:
            raise ConflictError("only succeeded risk assessment task can be exported")
        events = self.risk_service.repository.list_review_events(task.id)
        compiled_at = datetime.now(timezone.utc)
        projection = self.projector.project(
            business_code=task.business_code,
            generated_at=compiled_at,
            result=task.result_snapshot,
            review_events=events,
        )
        if projection is None:
            raise ConflictError("risk assessment result is unavailable")
        content = self.writer.write(projection=projection, compiled_at=compiled_at)
        filename = _safe_filename(
            f"供应链业务核对审计底稿_{task.business_code}.xlsx"
        )
        return ExportedRiskWorkbook(
            content=content,
            content_type=EXCEL_CONTENT_TYPE,
            content_disposition=f"attachment; filename*=UTF-8''{quote(filename)}",
        )


def _safe_filename(value: str) -> str:
    sanitized = _UNSAFE_FILENAME.sub("_", value).strip(" ._")
    return (sanitized or "供应链业务核对审计底稿.xlsx")[:180]

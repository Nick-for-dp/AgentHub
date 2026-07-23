from fastapi import APIRouter, Depends, Header, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.responses import APIResponse, success
from app.db.session import get_db
from app.core.enums import RiskAssessmentTaskStatus
from app.modules.auth.dependencies import get_current_subject
from app.modules.auth.schemas import AuthenticatedSubject
from app.modules.risk_assessment.schemas import (
    RiskAssessmentTaskCreate,
    RiskAssessmentDocumentAccessRead,
    RiskAssessmentTaskPageRead,
    RiskAssessmentTaskRead,
    RiskReviewSubmit,
)
from app.modules.risk_assessment.service import RiskAssessmentService
from app.modules.risk_assessment.export.service import RiskAuditWorkbookExportService


router = APIRouter()


def get_risk_assessment_service(db: Session = Depends(get_db)) -> RiskAssessmentService:
    return RiskAssessmentService(db)


def get_risk_export_service(
    db: Session = Depends(get_db),
) -> RiskAuditWorkbookExportService:
    return RiskAuditWorkbookExportService(db)


@router.get("/tasks", response_model=APIResponse[RiskAssessmentTaskPageRead])
def list_risk_assessment_tasks(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: RiskAssessmentTaskStatus | None = Query(default=None),
    subject: AuthenticatedSubject = Depends(get_current_subject),
    service: RiskAssessmentService = Depends(get_risk_assessment_service),
) -> APIResponse[RiskAssessmentTaskPageRead]:
    return success(
        service.list_tasks(
            subject=subject,
            page=page,
            page_size=page_size,
            status=status,
        )
    )


@router.post("/tasks", response_model=APIResponse[RiskAssessmentTaskRead])
def create_risk_assessment_task(
    payload: RiskAssessmentTaskCreate,
    subject: AuthenticatedSubject = Depends(get_current_subject),
    service: RiskAssessmentService = Depends(get_risk_assessment_service),
) -> APIResponse[RiskAssessmentTaskRead]:
    task = service.create_task(payload=payload, subject=subject)
    return success(service.to_read(task))


@router.get("/tasks/{task_id}", response_model=APIResponse[RiskAssessmentTaskRead])
def get_risk_assessment_task(
    task_id: str,
    subject: AuthenticatedSubject = Depends(get_current_subject),
    service: RiskAssessmentService = Depends(get_risk_assessment_service),
) -> APIResponse[RiskAssessmentTaskRead]:
    task = service.get_task(task_id=task_id, subject=subject)
    return success(service.to_read(task))


@router.delete("/tasks/{task_id}", response_model=APIResponse[None])
def delete_risk_assessment_task(
    task_id: str,
    subject: AuthenticatedSubject = Depends(get_current_subject),
    service: RiskAssessmentService = Depends(get_risk_assessment_service),
) -> APIResponse[None]:
    service.soft_delete_task(task_id=task_id, subject=subject)
    return success(None)


@router.post("/tasks/{task_id}/execute", response_model=APIResponse[RiskAssessmentTaskRead])
async def execute_risk_assessment_task(
    task_id: str,
    x_request_id: str | None = Header(default=None),
    subject: AuthenticatedSubject = Depends(get_current_subject),
    service: RiskAssessmentService = Depends(get_risk_assessment_service),
) -> APIResponse[RiskAssessmentTaskRead]:
    result = await service.execute_task(
        task_id=task_id,
        subject=subject,
        request_id=x_request_id,
    )
    return success(service.to_read(result))


@router.post("/tasks/{task_id}/reviews", response_model=APIResponse[RiskAssessmentTaskRead])
async def submit_risk_assessment_review(
    task_id: str,
    payload: RiskReviewSubmit,
    x_request_id: str | None = Header(default=None),
    subject: AuthenticatedSubject = Depends(get_current_subject),
    service: RiskAssessmentService = Depends(get_risk_assessment_service),
) -> APIResponse[RiskAssessmentTaskRead]:
    result = await service.submit_review(
        task_id=task_id,
        payload=payload,
        subject=subject,
        request_id=x_request_id,
    )
    return success(service.to_read(result))


@router.post("/tasks/{task_id}/cancel", response_model=APIResponse[RiskAssessmentTaskRead])
def cancel_risk_assessment_task(
    task_id: str,
    subject: AuthenticatedSubject = Depends(get_current_subject),
    service: RiskAssessmentService = Depends(get_risk_assessment_service),
) -> APIResponse[RiskAssessmentTaskRead]:
    task = service.cancel_task(task_id=task_id, subject=subject)
    return success(service.to_read(task))


@router.get(
    "/tasks/{task_id}/documents/{document_id}/access",
    response_model=APIResponse[RiskAssessmentDocumentAccessRead],
)
def get_risk_document_access(
    task_id: str,
    document_id: str,
    subject: AuthenticatedSubject = Depends(get_current_subject),
    service: RiskAssessmentService = Depends(get_risk_assessment_service),
) -> APIResponse[RiskAssessmentDocumentAccessRead]:
    return success(
        service.get_document_access(
            task_id=task_id,
            document_id=document_id,
            subject=subject,
        )
    )


@router.get("/tasks/{task_id}/export")
def export_risk_assessment_workbook(
    task_id: str,
    template_version: str = Query(default="risk-business-overview-v1"),
    subject: AuthenticatedSubject = Depends(get_current_subject),
    service: RiskAuditWorkbookExportService = Depends(get_risk_export_service),
) -> StreamingResponse:
    exported = service.export(
        task_id=task_id,
        subject=subject,
        template_version=template_version,
    )
    return StreamingResponse(
        exported.content,
        media_type=exported.content_type,
        headers={"Content-Disposition": exported.content_disposition},
    )

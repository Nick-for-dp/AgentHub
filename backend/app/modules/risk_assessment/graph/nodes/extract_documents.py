from langgraph.runtime import Runtime

from app.core.enums import DocumentTypeValidationStatus
from app.modules.file_parse.models import FileParseTask
from app.modules.risk_assessment.extraction.schemas import DocumentExtractionResult, DocumentType
from app.modules.risk_assessment.graph.state import RiskGraphContext, RiskGraphState


async def extract_documents(
    state: RiskGraphState,
    runtime: Runtime[RiskGraphContext],
) -> RiskGraphState:
    snapshots: list[dict] = []
    for document_id in state["document_ids"]:
        document = runtime.context.repository.get_document(document_id)
        if document is None:
            continue
        if document.extraction_snapshot:
            result = DocumentExtractionResult.model_validate(document.extraction_snapshot)
        else:
            parse_task = runtime.context.db.get(FileParseTask, document.file_parse_task_id)
            if parse_task is None:
                raise RuntimeError("file parse task not found during extraction")
            if runtime.context.extraction_service is None:
                raise RuntimeError("document extraction service is required for initial execution")
            result = await runtime.context.extraction_service.extract(
                file_parse_task=parse_task,
                declared_document_type=DocumentType(document.declared_document_type),
            )
            document.extraction_snapshot = result.model_dump(mode="json")
        if "DOCUMENT_TYPE_SUSPECTED" in result.warnings:
            validation_status = DocumentTypeValidationStatus.SUSPECTED
        elif "DOCUMENT_TYPE_UNVERIFIED" in result.warnings:
            validation_status = DocumentTypeValidationStatus.UNVERIFIED
        else:
            validation_status = DocumentTypeValidationStatus.MATCHED
        document.type_validation_status = validation_status
        document.type_validation_warnings = [
            warning for warning in result.warnings if warning.startswith("DOCUMENT_TYPE_")
        ]
        runtime.context.db.add(document)
        fields = []
        for field in result.fields:
            field_snapshot = field.model_dump(mode="json")
            field_snapshot["type_only_uncertainty"] = _is_type_only_uncertainty(
                field_snapshot,
                result.warnings,
            )
            fields.append(field_snapshot)
        snapshots.append(
            {
                "id": document.id,
                "file_parse_task_id": document.file_parse_task_id,
                "original_filename": document.original_filename,
                "document_type": document.declared_document_type,
                "type_validation_status": validation_status.value,
                "type_validation_warnings": list(document.type_validation_warnings),
                "fields": fields,
                "warnings": list(result.warnings),
                "parser_version": result.parser_version,
                "extractor_version": result.extractor_version,
                "provider_version": result.provider_version,
            }
        )
    runtime.context.db.commit()
    return {"documents": snapshots}


def _is_type_only_uncertainty(field: dict, warnings: list[str]) -> bool:
    field_code = field["field_code"]
    return (
        "DOCUMENT_TYPE_SUSPECTED" in warnings
        and field.get("status") == "UNCERTAIN"
        and not field.get("alternatives")
        and f"LOW_CONFIDENCE:{field_code}" not in warnings
        and f"EVIDENCE_MISSING:{field_code}" not in warnings
    )

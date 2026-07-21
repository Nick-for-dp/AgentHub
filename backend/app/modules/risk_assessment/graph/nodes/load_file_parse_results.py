from langgraph.runtime import Runtime

from app.core.enums import FileParseTaskStatus
from app.core.exceptions import ConflictError
from app.modules.file_parse.models import FileParseTask
from app.modules.risk_assessment.graph.state import RiskGraphContext, RiskGraphState


def load_file_parse_results(
    state: RiskGraphState,
    runtime: Runtime[RiskGraphContext],
) -> RiskGraphState:
    documents = runtime.context.repository.list_documents(state["task_id"])
    if not documents:
        raise ConflictError("risk assessment task has no documents")
    for document in documents:
        parse_task = runtime.context.db.get(FileParseTask, document.file_parse_task_id)
        if parse_task is None or parse_task.status != FileParseTaskStatus.SUCCEEDED:
            raise ConflictError("all file parse tasks must be succeeded")
        if not parse_task.original_filename:
            raise ConflictError("file parse task original filename is required")
        if not parse_task.result_snapshot or "metadata" not in parse_task.result_snapshot:
            raise ConflictError("file parse task has no ParsedDocumentV1 snapshot")
    return {"document_ids": [document.id for document in documents]}

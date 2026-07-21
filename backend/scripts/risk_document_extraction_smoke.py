"""Run the production risk-document provider against the controlled four-file sample set.

The script intentionally prints only field-status counts and evidence counts. It never prints
credentials, provider payloads, signed URLs, source bytes, quotes, or extracted business values.
"""

import argparse
import asyncio
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import get_settings
from app.core.enums import FileParseTaskStatus, RiskAssessmentTaskStatus, RiskReviewTargetKind
from app.core.exceptions import ConflictError
from app.integrations.file_reader.factory import parse_local_file
from app.modules.file_parse.models import FileParseTask
from app.modules.risk_assessment.extraction.provider_factory import (
    create_document_extraction_provider,
)
from app.modules.risk_assessment.extraction.schemas import DocumentType, FieldStatus
from app.modules.risk_assessment.extraction.service import DocumentExtractionService
from app.modules.risk_assessment.graph.executor import RiskGraphExecutor
from app.modules.risk_assessment.graph.state import RiskGraphContext
from app.modules.risk_assessment.models import (
    RiskAssessmentDocument,
    RiskAssessmentTask,
    RiskReviewEvent,
)


@dataclass(frozen=True)
class Sample:
    filename: str
    document_type: DocumentType


SAMPLES = (
    Sample(
        filename="1.供应链业务合同审批样表（宁夏吉元）.docx",
        document_type=DocumentType.APPROVAL_FORM,
    ),
    Sample(
        filename="2.71S采购合同.pdf",
        document_type=DocumentType.PURCHASE_CONTRACT,
    ),
    Sample(
        filename="5.01X销售合同.pdf",
        document_type=DocumentType.SALES_CONTRACT,
    ),
    Sample(
        filename="13.71S结算单.pdf",
        document_type=DocumentType.SETTLEMENT_STATEMENT,
    ),
)


class LocalSampleStorage:
    def __init__(self, content_by_key: dict[str, bytes]) -> None:
        self.content_by_key = content_by_key

    def download_bytes(self, *, bucket: str, object_key: str) -> bytes:
        if bucket != "risk-smoke":
            raise ValueError("unexpected smoke bucket")
        return self.content_by_key[object_key]


class GraphSmokeDB:
    def __init__(self, parse_tasks: dict[str, FileParseTask]) -> None:
        self.parse_tasks = parse_tasks

    def get(self, model, item_id):
        if model is FileParseTask:
            return self.parse_tasks.get(item_id)
        return None

    def add(self, value) -> None:
        del value

    def commit(self) -> None:
        return None

    def refresh(self, value) -> None:
        del value


class GraphSmokeRepository:
    def __init__(self, task, documents) -> None:
        self.task = task
        self.documents = {document.id: document for document in documents}
        self.review_events: dict[str, RiskReviewEvent] = {}

    def list_documents(self, task_id):
        if task_id != self.task.id:
            return []
        return list(self.documents.values())

    def get_document(self, document_id):
        return self.documents.get(document_id)

    def get_task(self, task_id, *, for_update=False):
        del for_update
        return self.task if task_id == self.task.id else None

    def get_review_event(self, event_id):
        return self.review_events.get(event_id)


class GraphSmokeCheckpointStore:
    def __init__(self) -> None:
        self.latest = None

    def put(self, *, task_id, thread_id, state, next_node, expected_version=None):
        current = self.latest.version if self.latest else 0
        if expected_version is not None and expected_version != current:
            raise ConflictError("risk graph checkpoint version conflict")
        self.latest = SimpleNamespace(
            task_id=task_id,
            thread_id=thread_id,
            checkpoint_id=f"checkpoint-{current + 1}",
            version=current + 1,
            state=state,
            next_node=next_node,
        )
        return self.latest

    def get_latest(self, thread_id):
        if self.latest and self.latest.thread_id == thread_id:
            return self.latest
        return None


class CachedExtractionService:
    def __init__(self, results_by_task_id) -> None:
        self.results_by_task_id = results_by_task_id
        self.calls: dict[str, int] = {}

    async def extract(self, *, file_parse_task, declared_document_type):
        del declared_document_type
        self.calls[file_parse_task.id] = self.calls.get(file_parse_task.id, 0) + 1
        return self.results_by_task_id[file_parse_task.id]


async def run(sample_dir: Path) -> int:
    paths = [(sample, sample_dir / sample.filename) for sample in SAMPLES]
    missing = [path.name for _, path in paths if not path.is_file()]
    if missing:
        print(json.dumps({"status": "failed", "missing_files": missing}, ensure_ascii=False))
        return 2

    settings = get_settings()
    provider = create_document_extraction_provider(settings)
    content_by_key = {path.name: path.read_bytes() for _, path in paths}
    service = DocumentExtractionService(
        provider=provider,
        storage=LocalSampleStorage(content_by_key),  # type: ignore[arg-type]
    )

    failures = 0
    parse_tasks: dict[str, FileParseTask] = {}
    results_by_task_id = {}
    for sample, path in paths:
        started = time.perf_counter()
        try:
            parsed_document = await parse_local_file(path)
            task = FileParseTask(
                id=f"parse-{len(parse_tasks) + 1}",
                source_uri=f"minio://risk-smoke/{path.name}",
                original_filename=path.name,
                file_type=parsed_document.metadata.file_type,
                reader_type=parsed_document.metadata.reader_type,
                status=FileParseTaskStatus.SUCCEEDED,
                result_snapshot=parsed_document.to_dict(),
            )
            result = await service.extract(
                file_parse_task=task,
                declared_document_type=sample.document_type,
            )
            parse_tasks[task.id] = task
            results_by_task_id[task.id] = result
            status_counts = {
                status.value: sum(field.status == status for field in result.fields)
                for status in FieldStatus
            }
            evidence_count = sum(len(field.sources) for field in result.fields)
            summary = {
                "status": "passed",
                "file": path.name,
                "document_type": sample.document_type.value,
                "parsed_blocks": len(parsed_document.blocks),
                "parse_warnings": [warning.code for warning in parsed_document.warnings],
                "field_status_counts": status_counts,
                "evidence_count": evidence_count,
                "result_warnings": result.warnings,
                "elapsed_seconds": round(time.perf_counter() - started, 2),
            }
        except Exception as exc:
            failures += 1
            summary = {
                "status": "failed",
                "file": path.name,
                "document_type": sample.document_type.value,
                "error_type": type(exc).__name__,
                "error": str(exc),
                "elapsed_seconds": round(time.perf_counter() - started, 2),
            }
        print(json.dumps(summary, ensure_ascii=False), flush=True)

    graph_summary = None
    if failures == 0:
        graph_summary = await _run_graph_acceptance(parse_tasks, results_by_task_id)
        if graph_summary["status"] != "passed":
            failures += 1
        print(json.dumps(graph_summary, ensure_ascii=False), flush=True)

    print(
        json.dumps(
            {
                "status": "passed" if failures == 0 else "failed",
                "samples": len(paths),
                "failures": failures,
                "provider_version": provider.version,
                "graph_acceptance": graph_summary,
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    return 0 if failures == 0 else 1


async def _run_graph_acceptance(parse_tasks, results_by_task_id) -> dict:
    task = RiskAssessmentTask(
        id="risk-smoke-task",
        agent_code="risk-assistant",
        business_code="RISK-SMOKE",
        status=RiskAssessmentTaskStatus.RUNNING,
    )
    documents = []
    for index, (sample, parse_task) in enumerate(zip(SAMPLES, parse_tasks.values(), strict=True)):
        documents.append(
            RiskAssessmentDocument(
                id=f"risk-document-{index + 1}",
                task_id=task.id,
                file_parse_task_id=parse_task.id,
                original_filename=parse_task.original_filename,
                declared_document_type=sample.document_type,
                document_order=index,
            )
        )
    repository = GraphSmokeRepository(task, documents)
    checkpoint = GraphSmokeCheckpointStore()
    extraction = CachedExtractionService(results_by_task_id)
    context = RiskGraphContext(
        db=GraphSmokeDB(parse_tasks),  # type: ignore[arg-type]
        repository=repository,  # type: ignore[arg-type]
        extraction_service=extraction,  # type: ignore[arg-type]
        checkpoint_store=checkpoint,  # type: ignore[arg-type]
    )
    executor = RiskGraphExecutor()
    outcome = await executor.execute(
        task_id=task.id,
        thread_id="risk-smoke-thread",
        context=context,
    )
    initial_state = "WAITING_REVIEW" if outcome.is_suspended else "SUCCEEDED"
    review_rounds = 0
    while outcome.is_suspended and review_rounds < 50:
        review_rounds += 1
        item = next(
            item
            for item in outcome.state.get("review_items", [])
            if not item.get("is_resolved")
        )
        target_kind = RiskReviewTargetKind(item["target_kind"])
        fact = outcome.state.get("facts", {}).get(item["target_code"], {})
        alternatives = list(fact.get("alternatives") or [])
        if target_kind == RiskReviewTargetKind.DOCUMENT_TYPE:
            action = "CONFIRM_DECLARED_TYPE"
            after_value = {"value": item.get("declared_document_type")}
        elif alternatives:
            action = "SELECT_VALUE"
            after_value = {"value": alternatives[0]}
        else:
            action = "MARK_MISSING"
            after_value = {"value": None}
        event = RiskReviewEvent(
            id=f"review-{review_rounds}",
            task_id=task.id,
            review_item_id=item["id"],
            target_kind=target_kind,
            target_code=item["target_code"],
            before_value={"value": fact.get("value")},
            alternatives=alternatives,
            after_value=after_value,
            action=action,
            reason="controlled smoke review",
            sources=list(fact.get("sources") or item.get("sources") or []),
            checkpoint_version=checkpoint.latest.version,
        )
        repository.review_events[event.id] = event
        outcome = await executor.resume(
            task_id=task.id,
            thread_id="risk-smoke-thread",
            review_event_id=event.id,
            expected_version=checkpoint.latest.version,
            context=context,
        )
    extraction_once = all(count == 1 for count in extraction.calls.values())
    passed = not outcome.is_suspended and extraction_once and len(extraction.calls) == len(documents)
    return {
        "status": "passed" if passed else "failed",
        "initial_state": initial_state,
        "final_state": outcome.state.get("execution_state"),
        "review_rounds": review_rounds,
        "documents": len(documents),
        "each_document_extracted_once": extraction_once,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "sample_dir",
        type=Path,
        help="Directory containing the controlled four-file risk-document sample set.",
    )
    args = parser.parse_args()
    return asyncio.run(run(args.sample_dir.resolve()))


if __name__ == "__main__":
    raise SystemExit(main())

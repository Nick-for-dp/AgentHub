import re
from collections import defaultdict
from typing import Any

from app.core.enums import FileParseTaskStatus
from app.core.exceptions import ConflictError
from app.integrations.file_reader.structure.schema import (
    InferredSection,
    NumberingInfo,
    ParsedBlock,
    ParsedDocumentV1,
    ParsedMetadata,
    SourceLocation,
    StructureWarning,
    StyleFeatures,
)
from app.integrations.object_storage import FileStorage, parse_storage_uri
from app.modules.file_parse.models import FileParseTask
from app.modules.risk_assessment.extraction.ports import DocumentExtractionProvider
from app.modules.risk_assessment.extraction.registry import create_document_extractor
from app.modules.risk_assessment.extraction.schemas import (
    DocumentExtractionResult,
    DocumentType,
    ExtractedField,
    FieldStatus,
    ScalarValue,
)


LOW_CONFIDENCE_THRESHOLD = 0.75
_NUMERIC_FIELD_MARKERS = ("quantity", "price", "amount", "ratio", "fee", "days", "payment")


class DocumentExtractionService:
    """把 file_parse_task 转成极简 DocumentExtractionResult。"""

    def __init__(self, *, provider: DocumentExtractionProvider, storage: FileStorage) -> None:
        self.provider = provider
        self.storage = storage

    async def extract(
        self,
        *,
        file_parse_task: FileParseTask,
        declared_document_type: DocumentType,
    ) -> DocumentExtractionResult:
        if file_parse_task.status != FileParseTaskStatus.SUCCEEDED:
            raise ConflictError("file parse task must be succeeded before extraction")
        if not file_parse_task.result_snapshot:
            raise ConflictError("file parse task has no parsed document snapshot")

        parsed_document = _parsed_document_from_snapshot(file_parse_task.result_snapshot)
        bucket, object_key = parse_storage_uri(file_parse_task.source_uri)
        source_content = self.storage.download_bytes(bucket=bucket, object_key=object_key)
        extractor = create_document_extractor(declared_document_type, self.provider)
        provider_fields, provider_warnings = await extractor.extract(
            parsed_document=parsed_document,
            source_filename=parsed_document.metadata.filename,
            source_content=source_content,
        )
        type_suspected = "DOCUMENT_TYPE_SUSPECTED" in provider_warnings
        fields, warnings = _assemble_fields(
            expected_field_codes=extractor.field_codes,
            provider_fields=provider_fields,
            parsed_document=parsed_document,
            type_suspected=type_suspected,
        )
        warnings = _deduplicate([*provider_warnings, *warnings])

        parser_version = (
            f"{parsed_document.metadata.reader_type}:"
            f"{parsed_document.metadata.structure_analyzer}"
        )
        return DocumentExtractionResult(
            document_type=declared_document_type,
            fields=fields,
            warnings=warnings,
            parser_version=parser_version,
            extractor_version=extractor.extractor_version,
            provider_version=self.provider.version,
        )


def _assemble_fields(
    *,
    expected_field_codes: tuple[str, ...],
    provider_fields: list[dict[str, Any]],
    parsed_document: ParsedDocumentV1,
    type_suspected: bool,
) -> tuple[list[ExtractedField], list[str]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    warnings: list[str] = []
    expected = set(expected_field_codes)
    for item in provider_fields:
        field_code = str(item.get("field_code") or "").strip()
        if field_code not in expected:
            if field_code:
                warnings.append(f"UNKNOWN_PROVIDER_FIELD:{field_code}")
            continue
        grouped[field_code].append(item)

    fields: list[ExtractedField] = []
    for field_code in expected_field_codes:
        items = grouped.get(field_code, [])
        field, field_warnings = _assemble_field(
            field_code=field_code,
            items=items,
            parsed_document=parsed_document,
            type_suspected=type_suspected,
        )
        fields.append(field)
        warnings.extend(field_warnings)
    return fields, _deduplicate(warnings)


def _assemble_field(
    *,
    field_code: str,
    items: list[dict[str, Any]],
    parsed_document: ParsedDocumentV1,
    type_suspected: bool,
) -> tuple[ExtractedField, list[str]]:
    if not items:
        return ExtractedField(field_code=field_code, status=FieldStatus.MISSING), []

    raw_values = [item.get("raw_value") for item in items if item.get("raw_value") is not None]
    if not raw_values:
        return ExtractedField(field_code=field_code, status=FieldStatus.MISSING), []

    valid_sources: list[dict[str, Any]] = []
    alternatives: list[ScalarValue] = []
    confidence_is_low = False
    for item in items:
        valid_sources.extend(_valid_sources(item.get("sources"), parsed_document))
        alternatives.extend(_scalar_values(item.get("alternatives")))
        confidence = item.get("confidence")
        if isinstance(confidence, (int, float)) and confidence < LOW_CONFIDENCE_THRESHOLD:
            confidence_is_low = True

    distinct_values = _deduplicate(raw_values + alternatives)
    chosen = raw_values[0]
    normalized = items[0].get("normalized_value")
    if normalized is None:
        normalized = _normalize_value(field_code, chosen)

    is_uncertain = (
        type_suspected
        or confidence_is_low
        or not valid_sources
        or len(distinct_values) > 1
    )
    warnings: list[str] = []
    if not valid_sources:
        warnings.append(f"EVIDENCE_MISSING:{field_code}")
    if confidence_is_low:
        warnings.append(f"LOW_CONFIDENCE:{field_code}")

    return (
        ExtractedField(
            field_code=field_code,
            raw_value=chosen,
            normalized_value=normalized,
            unit=items[0].get("unit"),
            status=FieldStatus.UNCERTAIN if is_uncertain else FieldStatus.FOUND,
            sources=valid_sources,
            alternatives=distinct_values if len(distinct_values) > 1 else [],
        ),
        warnings,
    )


def _valid_sources(value: Any, parsed_document: ParsedDocumentV1) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    blocks = {block.id: block for block in parsed_document.blocks}
    page_count = parsed_document.metadata.page_count
    valid: list[dict[str, Any]] = []
    for source in value:
        if not isinstance(source, dict):
            continue
        block_id = source.get("block_id")
        page_number = source.get("page_number")
        quote = str(source.get("quote") or "").strip()
        block = blocks.get(str(block_id)) if block_id else None
        block_valid = block is not None and (not quote or quote in block.text)
        page_valid = (
            isinstance(page_number, int)
            and page_number > 0
            and (page_count is None or page_number <= page_count)
        )
        if block_valid or page_valid:
            clean_source = {
                key: source[key]
                for key in ("block_id", "page_number", "quote", "bbox")
                if source.get(key) not in (None, "")
            }
            valid.append(clean_source)
    return valid


def _normalize_value(field_code: str, value: ScalarValue) -> ScalarValue:
    if not isinstance(value, str):
        return value
    stripped = " ".join(value.split())
    if any(marker in field_code for marker in _NUMERIC_FIELD_MARKERS):
        match = re.search(r"-?\d[\d,]*(?:\.\d+)?", stripped)
        if match:
            return match.group(0).replace(",", "")
    return stripped


def _parsed_document_from_snapshot(snapshot: dict[str, Any]) -> ParsedDocumentV1:
    metadata = ParsedMetadata(**snapshot["metadata"])
    blocks = [
        ParsedBlock(
            id=item["id"],
            kind=item["kind"],
            text=item["text"],
            order=item["order"],
            source_location=SourceLocation(**item.get("source_location", {})),
            style_features=StyleFeatures(**item.get("style_features", {})),
            metadata=item.get("metadata", {}),
        )
        for item in snapshot.get("blocks", [])
    ]
    sections: list[InferredSection] = []
    for item in snapshot.get("sections", []):
        numbering = item.get("numbering")
        sections.append(
            InferredSection(
                id=item["id"],
                title=item["title"],
                level=item["level"],
                heading_block_id=item["heading_block_id"],
                parent_id=item.get("parent_id"),
                block_ids=item.get("block_ids", []),
                numbering=NumberingInfo(**numbering) if numbering else None,
                confidence=item.get("confidence", 0.0),
            )
        )
    warnings = [StructureWarning(**item) for item in snapshot.get("warnings", [])]
    return ParsedDocumentV1(
        metadata=metadata,
        blocks=blocks,
        sections=sections,
        warnings=warnings,
    )


def _scalar_values(value: Any) -> list[ScalarValue]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, (str, int, float, bool))]


def _deduplicate(values: list[Any]) -> list[Any]:
    result: list[Any] = []
    for value in values:
        if value not in result:
            result.append(value)
    return result

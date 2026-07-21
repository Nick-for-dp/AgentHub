from abc import ABC
from typing import Any

from app.integrations.file_reader.structure.schema import ParsedDocumentV1
from app.modules.risk_assessment.extraction.ports import DocumentExtractionProvider
from app.modules.risk_assessment.extraction.schemas import DocumentType
from app.modules.risk_assessment.extraction.document_type_validation import (
    validate_document_type,
)


class BaseDocumentExtractor(ABC):
    """四类 extractor 的共享薄层；每份文档只调用一次 provider。"""

    document_type: DocumentType
    field_codes: tuple[str, ...]
    prompt: str
    prompt_version = "v1"
    extractor_version = "v1"
    expected_title_markers: tuple[str, ...] = ()
    conflicting_title_markers: tuple[str, ...] = ()

    def __init__(self, provider: DocumentExtractionProvider) -> None:
        self.provider = provider

    async def extract(
        self,
        *,
        parsed_document: ParsedDocumentV1,
        source_filename: str,
        source_content: bytes,
    ) -> tuple[list[dict[str, Any]], list[str]]:
        return await self.provider.extract(
            document_type=self.document_type,
            parsed_document=parsed_document,
            source_filename=source_filename,
            source_content=source_content,
            field_codes=self.field_codes,
            prompt=self.prompt,
            prompt_version=self.prompt_version,
            expected_title_markers=self.expected_title_markers,
            conflicting_title_markers=self.conflicting_title_markers,
        )

    def is_document_type_suspected(self, parsed_document: ParsedDocumentV1) -> bool:
        validation = validate_document_type(
            declared_type=self.document_type,
            original_filename=parsed_document.metadata.filename,
            block_texts=(block.text for block in parsed_document.blocks),
            expected_markers=self.expected_title_markers,
            conflicting_markers=self.conflicting_title_markers,
        )
        return validation.status.value == "SUSPECTED"


DocumentExtractor = BaseDocumentExtractor

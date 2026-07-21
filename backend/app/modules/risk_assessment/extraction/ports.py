from typing import Any, Protocol

from app.integrations.file_reader.structure.schema import ParsedDocumentV1
from app.modules.risk_assessment.extraction.schemas import DocumentType


class DocumentExtractionProvider(Protocol):
    """OCR/VLM/文本模型的单一一期抽取端口。"""

    version: str

    async def extract(
        self,
        *,
        document_type: DocumentType,
        parsed_document: ParsedDocumentV1,
        source_filename: str,
        source_content: bytes,
        field_codes: tuple[str, ...],
        prompt: str,
        prompt_version: str,
        expected_title_markers: tuple[str, ...],
        conflicting_title_markers: tuple[str, ...],
    ) -> tuple[list[dict[str, Any]], list[str]]:
        """返回临时字段字典和稳定 warning；service 随即归一化。"""

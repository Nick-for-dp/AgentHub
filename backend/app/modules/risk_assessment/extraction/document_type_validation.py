from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import PureWindowsPath
from typing import Iterable

from app.core.enums import DocumentTypeValidationStatus
from app.modules.risk_assessment.extraction.schemas import DocumentType


DOCUMENT_TYPE_VALIDATION_VERSION = "document-type-validation-v1"
DOCUMENT_TYPE_SUSPECTED = "DOCUMENT_TYPE_SUSPECTED"
DOCUMENT_TYPE_UNVERIFIED = "DOCUMENT_TYPE_UNVERIFIED"
TYPE_MARKER_HEADER_CHAR_LIMIT = 160


@dataclass(frozen=True)
class DocumentTypeValidationResult:
    status: DocumentTypeValidationStatus
    reason_codes: tuple[str, ...] = ()

    @property
    def warnings(self) -> list[str]:
        if self.status == DocumentTypeValidationStatus.SUSPECTED:
            return [DOCUMENT_TYPE_SUSPECTED]
        if self.status == DocumentTypeValidationStatus.UNVERIFIED:
            return [DOCUMENT_TYPE_UNVERIFIED]
        return []


def validate_document_type(
    *,
    declared_type: DocumentType,
    original_filename: str,
    block_texts: Iterable[str],
    expected_markers: tuple[str, ...],
    conflicting_markers: tuple[str, ...],
) -> DocumentTypeValidationResult:
    """以正文为主、文件名为弱提示校验调用方声明类型。"""
    del declared_type
    content = _normalize("\n".join(block_texts))
    header_content = content[:TYPE_MARKER_HEADER_CHAR_LIMIT]
    filename = _normalize(PureWindowsPath(original_filename).name)
    expected_content = _matched(expected_markers, header_content)
    conflicting_content = _matched(conflicting_markers, header_content)
    non_header_markers = (
        set(_matched(expected_markers, content))
        | set(_matched(conflicting_markers, content))
    ) - set(expected_content) - set(conflicting_content)
    filename_expected = _matched(expected_markers, filename)
    filename_conflicting = _matched(conflicting_markers, filename)

    reasons: list[str] = []
    if filename_expected:
        reasons.append("FILENAME_EXPECTED_HINT")
    if filename_conflicting:
        reasons.append("FILENAME_CONFLICT_HINT")
    if expected_content:
        reasons.append("CONTENT_EXPECTED_MARKER")
    if conflicting_content:
        reasons.append("CONTENT_CONFLICT_MARKER")
    if non_header_markers:
        reasons.append("NON_HEADER_DOCUMENT_MARKER_IGNORED")

    if conflicting_content and expected_content:
        reasons.append("CONTENT_MARKERS_AMBIGUOUS")
        return DocumentTypeValidationResult(
            status=DocumentTypeValidationStatus.SUSPECTED,
            reason_codes=tuple(reasons),
        )
    if len(conflicting_content) == 1:
        return DocumentTypeValidationResult(
            status=DocumentTypeValidationStatus.SUSPECTED,
            reason_codes=tuple(reasons),
        )
    if len(conflicting_content) > 1:
        reasons.append("MULTIPLE_DOCUMENT_MARKERS")
        return DocumentTypeValidationResult(
            status=DocumentTypeValidationStatus.UNVERIFIED,
            reason_codes=tuple(reasons),
        )
    if expected_content:
        return DocumentTypeValidationResult(
            status=DocumentTypeValidationStatus.MATCHED,
            reason_codes=tuple(reasons),
        )
    reasons.append("CONTENT_TYPE_MARKER_MISSING")
    return DocumentTypeValidationResult(
        status=DocumentTypeValidationStatus.UNVERIFIED,
        reason_codes=tuple(reasons),
    )


def _matched(markers: tuple[str, ...], normalized_text: str) -> tuple[str, ...]:
    return tuple(marker for marker in markers if _normalize(marker) in normalized_text)


def _normalize(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).lower()
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", normalized)

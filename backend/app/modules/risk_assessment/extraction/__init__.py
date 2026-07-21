"""一期文档字段抽取的极简公共入口。"""

from app.modules.risk_assessment.extraction.schemas import (
    DocumentExtractionResult,
    DocumentType,
    ExtractedField,
    FieldStatus,
)
from app.modules.risk_assessment.extraction.service import DocumentExtractionService

__all__ = [
    "DocumentExtractionResult",
    "DocumentExtractionService",
    "DocumentType",
    "ExtractedField",
    "FieldStatus",
]

from collections.abc import Callable

from app.modules.risk_assessment.extraction.base import BaseDocumentExtractor
from app.modules.risk_assessment.extraction.extractors import (
    ApprovalFormExtractor,
    PurchaseContractExtractor,
    SalesContractExtractor,
    SettlementStatementExtractor,
)
from app.modules.risk_assessment.extraction.ports import DocumentExtractionProvider
from app.modules.risk_assessment.extraction.schemas import DocumentType


_EXTRACTORS: dict[DocumentType, Callable[[DocumentExtractionProvider], BaseDocumentExtractor]] = {
    DocumentType.PURCHASE_CONTRACT: PurchaseContractExtractor,
    DocumentType.SALES_CONTRACT: SalesContractExtractor,
    DocumentType.APPROVAL_FORM: ApprovalFormExtractor,
    DocumentType.SETTLEMENT_STATEMENT: SettlementStatementExtractor,
}


def create_document_extractor(
    document_type: DocumentType,
    provider: DocumentExtractionProvider,
) -> BaseDocumentExtractor:
    """按调用方声明类型创建新的专用 extractor。"""
    try:
        factory = _EXTRACTORS[document_type]
    except KeyError as exc:
        raise ValueError(f"unsupported declared document type: {document_type}") from exc
    return factory(provider)

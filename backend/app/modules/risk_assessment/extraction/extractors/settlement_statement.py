from app.modules.risk_assessment.extraction.base import BaseDocumentExtractor
from app.modules.risk_assessment.extraction.schemas import DocumentType


class SettlementStatementExtractor(BaseDocumentExtractor):
    document_type = DocumentType.SETTLEMENT_STATEMENT
    extractor_version = "settlement-statement-v1"
    prompt_version = "settlement-statement-prompt-v1"
    field_codes = (
        "settlement_quantity",
        "settlement_amount",
        "floating_fee",
        "occupied_days",
        "supplementary_payment",
    )
    prompt = (
        "从结算单中只提取指定字段。必须返回原文来源；没有明确记录时返回空值，"
        "不得根据合同费率计算。"
    )
    expected_title_markers = ("结算单",)
    conflicting_title_markers = ("采购合同", "销售合同", "业务审批表")

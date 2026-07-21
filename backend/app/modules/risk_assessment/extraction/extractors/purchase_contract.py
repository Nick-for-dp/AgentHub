from app.modules.risk_assessment.extraction.base import BaseDocumentExtractor
from app.modules.risk_assessment.extraction.schemas import DocumentType


class PurchaseContractExtractor(BaseDocumentExtractor):
    document_type = DocumentType.PURCHASE_CONTRACT
    extractor_version = "purchase-contract-v1"
    prompt_version = "purchase-contract-prompt-v1"
    field_codes = (
        "upstream_supplier",
        "purchase_contract_number",
        "purchase_signing_date",
        "goods_name",
        "purchase_quantity",
        "purchase_unit_price_tax_included",
        "purchase_amount_tax_included",
        "key_customer_discount",
        "deposit_ratio",
        "deposit_amount",
    )
    prompt = (
        "从采购合同中只提取指定字段。每个非空字段必须返回原文来源；"
        "不能确认时返回空值，不得计算或推测。"
    )
    expected_title_markers = ("采购合同",)
    conflicting_title_markers = ("销售合同", "结算单", "业务审批表")

from app.modules.risk_assessment.extraction.base import BaseDocumentExtractor
from app.modules.risk_assessment.extraction.schemas import DocumentType


class SalesContractExtractor(BaseDocumentExtractor):
    document_type = DocumentType.SALES_CONTRACT
    extractor_version = "sales-contract-v1"
    prompt_version = "sales-contract-prompt-v1"
    field_codes = (
        "downstream_customer",
        "sales_contract_number",
        "sales_signing_date",
        "delivery_location",
        "goods_name",
        "sales_quantity",
        "sales_unit_price_tax_included",
        "sales_amount_tax_included",
    )
    prompt = (
        "从销售合同中只提取指定字段。下游客户按买受人/需方等功能角色识别；"
        "每个非空字段必须返回原文来源，不得按甲乙方位置猜测。"
    )
    expected_title_markers = ("销售合同",)
    conflicting_title_markers = ("采购合同", "结算单", "业务审批表")

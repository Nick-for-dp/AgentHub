from app.modules.risk_assessment.extraction.base import BaseDocumentExtractor
from app.modules.risk_assessment.extraction.schemas import DocumentType


class ApprovalFormExtractor(BaseDocumentExtractor):
    document_type = DocumentType.APPROVAL_FORM
    extractor_version = "approval-form-v2"
    prompt_version = "approval-form-prompt-v2"
    field_codes = (
        "raw_business_mode_text",
        "upstream_supplier_raw",
        "downstream_customer_raw",
        "approval_quantity",
        "approval_purchase_unit_price",
        "approval_sales_unit_price",
        "approval_purchase_amount",
        "approval_sales_amount",
    )
    prompt = (
        "从供应链业务审批表中只提取指定字段。raw_business_mode_text 只能来自"
        "‘业务性质’栏的已勾选项及其填写内容，禁止使用‘业务模式简介’长文本。"
        "业务模式不映射正式枚举；没有来源的值不得输出。"
    )
    expected_title_markers = ("供应链业务合同审批", "供应链业务审批", "业务审批表")
    conflicting_title_markers = ("采购合同", "销售合同", "结算单")

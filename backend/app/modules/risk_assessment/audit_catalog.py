from dataclasses import dataclass

from app.modules.risk_assessment.extraction.schemas import DocumentType


AUDIT_CATALOG_VERSION = "audit-field-policy-v1"


@dataclass(frozen=True)
class AuditFieldDefinition:
    code: str
    label: str
    document_types: tuple[DocumentType, ...]
    unit: str | None
    critical: bool


AUDIT_FIELDS: tuple[AuditFieldDefinition, ...] = (
    AuditFieldDefinition("raw_business_mode_text", "业务模式原文", (DocumentType.APPROVAL_FORM,), None, False),
    AuditFieldDefinition("upstream_supplier_raw", "审批上游供应商原文", (DocumentType.APPROVAL_FORM,), None, False),
    AuditFieldDefinition("downstream_customer_raw", "审批下游客户原文", (DocumentType.APPROVAL_FORM,), None, False),
    AuditFieldDefinition("approval_quantity", "审批数量", (DocumentType.APPROVAL_FORM,), "TON", True),
    AuditFieldDefinition("approval_purchase_unit_price", "审批采购单价", (DocumentType.APPROVAL_FORM,), "CNY/TON", True),
    AuditFieldDefinition("approval_sales_unit_price", "审批销售单价", (DocumentType.APPROVAL_FORM,), "CNY/TON", True),
    AuditFieldDefinition("approval_purchase_amount", "审批采购金额", (DocumentType.APPROVAL_FORM,), "CNY", True),
    AuditFieldDefinition("approval_sales_amount", "审批销售金额", (DocumentType.APPROVAL_FORM,), "CNY", True),
    AuditFieldDefinition("upstream_supplier", "上游供应商", (DocumentType.PURCHASE_CONTRACT,), None, True),
    AuditFieldDefinition("purchase_contract_number", "采购合同号", (DocumentType.PURCHASE_CONTRACT,), None, True),
    AuditFieldDefinition("purchase_signing_date", "采购合同签订日", (DocumentType.PURCHASE_CONTRACT,), "DATE", False),
    AuditFieldDefinition("goods_name", "货物名称", (DocumentType.PURCHASE_CONTRACT, DocumentType.SALES_CONTRACT), None, True),
    AuditFieldDefinition("purchase_quantity", "采购合同数量", (DocumentType.PURCHASE_CONTRACT,), "TON", True),
    AuditFieldDefinition("purchase_unit_price_tax_included", "采购含税单价", (DocumentType.PURCHASE_CONTRACT,), "CNY/TON", True),
    AuditFieldDefinition("purchase_amount_tax_included", "采购含税金额", (DocumentType.PURCHASE_CONTRACT,), "CNY", True),
    AuditFieldDefinition("key_customer_discount", "大客户优惠", (DocumentType.PURCHASE_CONTRACT,), "CNY", False),
    AuditFieldDefinition("deposit_ratio", "保证金比例", (DocumentType.PURCHASE_CONTRACT,), "PERCENT", True),
    AuditFieldDefinition("deposit_amount", "保证金金额", (DocumentType.PURCHASE_CONTRACT,), "CNY", False),
    AuditFieldDefinition("downstream_customer", "下游客户", (DocumentType.SALES_CONTRACT,), None, True),
    AuditFieldDefinition("sales_contract_number", "销售合同号", (DocumentType.SALES_CONTRACT,), None, True),
    AuditFieldDefinition("sales_signing_date", "销售合同签订日", (DocumentType.SALES_CONTRACT,), "DATE", False),
    AuditFieldDefinition("delivery_location", "交货地点", (DocumentType.SALES_CONTRACT,), None, False),
    AuditFieldDefinition("sales_quantity", "销售合同数量", (DocumentType.SALES_CONTRACT,), "TON", True),
    AuditFieldDefinition("sales_unit_price_tax_included", "销售含税单价", (DocumentType.SALES_CONTRACT,), "CNY/TON", True),
    AuditFieldDefinition("sales_amount_tax_included", "销售含税金额", (DocumentType.SALES_CONTRACT,), "CNY", True),
    AuditFieldDefinition("settlement_quantity", "结算数量", (DocumentType.SETTLEMENT_STATEMENT,), "TON", True),
    AuditFieldDefinition("settlement_amount", "结算金额", (DocumentType.SETTLEMENT_STATEMENT,), "CNY", True),
    AuditFieldDefinition("floating_fee", "浮动费", (DocumentType.SETTLEMENT_STATEMENT,), "CNY", False),
    AuditFieldDefinition("occupied_days", "资金占用天数", (DocumentType.SETTLEMENT_STATEMENT,), "DAY", False),
    AuditFieldDefinition("supplementary_payment", "补款金额", (DocumentType.SETTLEMENT_STATEMENT,), "CNY", False),
)

AUDIT_FIELD_BY_CODE = {item.code: item for item in AUDIT_FIELDS}


def is_critical_field(field_code: str) -> bool:
    definition = AUDIT_FIELD_BY_CODE.get(field_code)
    return bool(definition and definition.critical)

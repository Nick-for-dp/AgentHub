from dataclasses import dataclass


@dataclass(frozen=True)
class BusinessOverviewDefinition:
    code: str
    label: str
    field_codes: tuple[str, ...]
    formatter: str = "direct"


BUSINESS_OVERVIEW_DEFINITIONS: tuple[BusinessOverviewDefinition, ...] = (
    BusinessOverviewDefinition("business_mode", "业务模式", ("raw_business_mode_text",)),
    BusinessOverviewDefinition("upstream_supplier", "上游供应商", ("upstream_supplier",)),
    BusinessOverviewDefinition("downstream_customer", "下游客户", ("downstream_customer",)),
    BusinessOverviewDefinition("goods_name", "货物名称", ("goods_name",)),
    BusinessOverviewDefinition(
        "purchase_contract_number", "采购合同号", ("purchase_contract_number",)
    ),
    BusinessOverviewDefinition(
        "sales_contract_number", "销售合同号", ("sales_contract_number",)
    ),
    BusinessOverviewDefinition(
        "purchase_signing_date", "采购合同签订日", ("purchase_signing_date",)
    ),
    BusinessOverviewDefinition(
        "sales_signing_date", "销售合同签订日", ("sales_signing_date",)
    ),
    BusinessOverviewDefinition("delivery_location", "交货地点", ("delivery_location",)),
    BusinessOverviewDefinition(
        "purchase_unit_price_tax_included",
        "采购含税单价",
        ("purchase_unit_price_tax_included",),
    ),
    BusinessOverviewDefinition(
        "sales_unit_price_tax_included",
        "销售含税单价",
        ("sales_unit_price_tax_included",),
    ),
    BusinessOverviewDefinition(
        "contract_quantity",
        "合同约定数量",
        ("purchase_quantity", "sales_quantity"),
        "contract_quantity",
    ),
    BusinessOverviewDefinition(
        "purchase_amount_tax_included",
        "采购合同含税金额",
        ("purchase_amount_tax_included",),
    ),
    BusinessOverviewDefinition(
        "sales_amount_tax_included",
        "销售合同含税金额",
        ("sales_amount_tax_included",),
    ),
    BusinessOverviewDefinition(
        "key_customer_discount", "大客户优惠", ("key_customer_discount",)
    ),
    BusinessOverviewDefinition(
        "deposit",
        "保证金比例",
        ("deposit_ratio", "deposit_amount"),
        "deposit",
    ),
    BusinessOverviewDefinition(
        "floating_fee",
        "浮动费",
        ("floating_fee", "occupied_days"),
        "floating_fee",
    ),
)

BUSINESS_OVERVIEW_BY_CODE = {
    definition.code: definition for definition in BUSINESS_OVERVIEW_DEFINITIONS
}

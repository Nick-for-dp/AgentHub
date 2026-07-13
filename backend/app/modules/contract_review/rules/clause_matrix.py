"""A1-A7 对手方等级与条款分类的敏感性矩阵。

``True`` 表示敏感条款，需要走审批；``False`` 表示非敏感，可进入优化路径。
A1 为最低资信，A7 为最高资信。MVP 先按现有“资信-条款矩阵”压平成七档：

- A1: 低级资信
- A2: 中级资信 / 全国民营企业200强
- A3: 中级资信 / 省属国企三级子公司
- A4: 中级资信 / 央企四级子公司
- A5: 高级资信 / 全国民营企业100强
- A6: 高级资信 / 省属国企二级以内子公司
- A7: 高级资信 / 央企三级以内子公司

后续若业务部门确认 A1-A7 的正式定义，只需要调整本矩阵和
``counterparty_level_mapper``。
"""

from app.core.enums import CounterpartyLevel

CLAUSE_CATEGORY_LABELS: dict[str, str] = {
    "cargo_acceptance": "货物验收条款",
    "document_authenticity": "单据真实性条款",
    "liability": "责任条款",
    "no_lien": "无留置权",
    "loss_compensation": "损失赔偿条款",
    "dispute_arbitration": "争议解决(仲裁)",
    "unfavorable_litigation": "争议解决(诉讼不利)",
    "operation_process": "操作流程条款",
    "holiday_sms_pickup_limit": "节假日短信提货量条款",
}

CLAUSE_SENSITIVE_MATRIX: dict[CounterpartyLevel, dict[str, bool]] = {
    CounterpartyLevel.A1: {
        "cargo_acceptance": True,
        "document_authenticity": True,
        "liability": True,
        "no_lien": True,
        "loss_compensation": True,
        "dispute_arbitration": True,
        "unfavorable_litigation": True,
        "operation_process": True,
        "holiday_sms_pickup_limit": True,
    },
    CounterpartyLevel.A2: {
        "cargo_acceptance": True,
        "document_authenticity": True,
        "liability": True,
        "no_lien": True,
        "loss_compensation": False,
        "dispute_arbitration": True,
        "unfavorable_litigation": True,
        "operation_process": True,
        "holiday_sms_pickup_limit": False,
    },
    CounterpartyLevel.A3: {
        "cargo_acceptance": True,
        "document_authenticity": True,
        "liability": True,
        "no_lien": False,
        "loss_compensation": False,
        "dispute_arbitration": True,
        "unfavorable_litigation": False,
        "operation_process": True,
        "holiday_sms_pickup_limit": False,
    },
    CounterpartyLevel.A4: {
        "cargo_acceptance": True,
        "document_authenticity": True,
        "liability": True,
        "no_lien": False,
        "loss_compensation": False,
        "dispute_arbitration": True,
        "unfavorable_litigation": False,
        "operation_process": True,
        "holiday_sms_pickup_limit": False,
    },
    CounterpartyLevel.A5: {
        "cargo_acceptance": True,
        "document_authenticity": True,
        "liability": False,
        "no_lien": False,
        "loss_compensation": False,
        "dispute_arbitration": True,
        "unfavorable_litigation": False,
        "operation_process": True,
        "holiday_sms_pickup_limit": False,
    },
    CounterpartyLevel.A6: {
        "cargo_acceptance": False,
        "document_authenticity": True,
        "liability": False,
        "no_lien": False,
        "loss_compensation": False,
        "dispute_arbitration": True,
        "unfavorable_litigation": False,
        "operation_process": True,
        "holiday_sms_pickup_limit": False,
    },
    CounterpartyLevel.A7: {
        "cargo_acceptance": False,
        "document_authenticity": True,
        "liability": False,
        "no_lien": False,
        "loss_compensation": False,
        "dispute_arbitration": True,
        "unfavorable_litigation": False,
        "operation_process": True,
        "holiday_sms_pickup_limit": False,
    },
}

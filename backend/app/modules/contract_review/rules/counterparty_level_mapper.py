from app.core.enums import CounterpartyLevel


def normalize_counterparty_level(value: str | CounterpartyLevel) -> CounterpartyLevel:
    """校验并归一化合同对手方资信等级。

    MVP 由调用方直接传入 ``A1``-``A7``。后续如果需要根据客户性质、客户层级、
    统一社会信用代码或主数据档案推导等级，应在本模块新增映射函数，避免把映射逻辑
    分散到 API、执行器或规则引擎中。
    """
    if isinstance(value, CounterpartyLevel):
        return value
    return CounterpartyLevel(str(value).strip().upper())

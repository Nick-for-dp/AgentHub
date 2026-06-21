"""时间序列化工具。

平台约定：数据库统一存储 UTC 时间（连接层 `time_zone='+00:00'`，
应用层 `utcnow()` 写入带 UTC 时区的时间）。对外 API 响应统一序列化为
北京时间（UTC+8）的 ISO 8601 字符串（带 `+08:00` 偏移），前端可无歧义解析。

从 MySQL 读出的 DATETIME 不带时区信息（tzinfo=None），需先按 UTC 解释，
再转换为北京时间输出。
"""

from datetime import datetime, timedelta, timezone
from typing import Annotated

from pydantic import PlainSerializer

# 北京时区固定为 UTC+8（中国不使用夏令时）
BEIJING_TZ = timezone(timedelta(hours=8))


def to_beijing_iso(value: datetime | None) -> str | None:
    """将存储的 UTC 时间序列化为北京时间 ISO 字符串（带 +08:00 偏移）。

    naive datetime（来自 MySQL DATETIME，无 tzinfo）按 UTC 解释；
    带时区的 datetime 直接转换。空值返回 None。
    """
    if value is None:
        return None
    aware = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
    return aware.astimezone(BEIJING_TZ).isoformat()


# 响应 schema 中的 datetime 字段统一使用此类型，自动转北京时间输出。
# 查询参数等输入侧仍用普通 datetime，不受影响。
BeijingDateTime = Annotated[datetime, PlainSerializer(to_beijing_iso, return_type=str | None)]

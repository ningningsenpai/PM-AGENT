"""业务时间的统一生成、比较和序列化。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

try:
    SHANGHAI_TIMEZONE = ZoneInfo("Asia/Shanghai")
except ZoneInfoNotFoundError:
    # Windows 精简运行时可能不含 IANA 数据；上海现行业务时区固定为 UTC+08:00。
    SHANGHAI_TIMEZONE = timezone(timedelta(hours=8), "Asia/Shanghai")


def shanghai_now() -> datetime:
    """返回带上海时区偏移的当前时间。"""
    return datetime.now(SHANGHAI_TIMEZONE)


def shanghai_now_naive() -> datetime:
    """返回适合写入 MySQL DATETIME 的上海本地无时区时间。"""
    return shanghai_now().replace(tzinfo=None)


def as_shanghai(value: datetime) -> datetime:
    """把时间统一为上海时区；旧无时区值按上海时间解释。"""
    if value.tzinfo is None:
        return value.replace(tzinfo=SHANGHAI_TIMEZONE)
    return value.astimezone(SHANGHAI_TIMEZONE)


def shanghai_naive(value: datetime) -> datetime:
    """把任意时间转换为上海本地 DATETIME 表示。"""
    return as_shanghai(value).replace(tzinfo=None)


def shanghai_iso(value: datetime) -> str:
    """输出带 +08:00 偏移的 RFC 3339 时间。"""
    return as_shanghai(value).isoformat()


def legacy_utc_to_shanghai(value: datetime) -> datetime:
    """仅供旧 Context 数据迁移：旧无时区值按 UTC 语义读取。"""
    source = value.replace(tzinfo=UTC) if value.tzinfo is None else value
    return source.astimezone(SHANGHAI_TIMEZONE)

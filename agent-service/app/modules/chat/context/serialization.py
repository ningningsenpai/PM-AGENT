"""上下文日期与接口视图转换，不触发持久化操作。"""

from datetime import UTC

from .schemas import EntryView


def utc_naive(value):
    return (
        value.astimezone(UTC).replace(tzinfo=None) if value and value.tzinfo else value
    )


def entry_data(row):
    return EntryView.model_validate(row).model_dump(mode="json", by_alias=True)

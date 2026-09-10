"""统一上海业务时间工具测试。"""

from datetime import UTC, datetime

from app.core.response import ApiResponse
from app.core.schemas import Schema
from app.core.time import (
    ShanghaiDateTime,
    as_shanghai,
    legacy_utc_to_shanghai,
    shanghai_iso,
    shanghai_naive,
)


class TimePayload(Schema):
    occurred_at: ShanghaiDateTime


def test_naive_time_is_interpreted_as_shanghai_time() -> None:
    value = datetime(2026, 9, 10, 10, 30)

    assert shanghai_iso(value) == "2026-09-10T10:30:00+08:00"
    assert shanghai_naive(value) == value


def test_utc_time_is_converted_to_shanghai_time() -> None:
    value = datetime(2026, 9, 10, 2, 30, tzinfo=UTC)

    assert as_shanghai(value).isoformat() == "2026-09-10T10:30:00+08:00"
    assert legacy_utc_to_shanghai(value).isoformat() == "2026-09-10T10:30:00+08:00"


def test_schema_and_response_emit_offset_for_nested_time() -> None:
    value = datetime(2026, 9, 10, 10, 30)
    payload = TimePayload(occurred_at=value)
    response = ApiResponse(
        data={"payload": payload, "legacyTime": value},
        traceId="trace",
    )

    assert payload.model_dump(mode="json", by_alias=True)["occurredAt"].endswith(
        "+08:00"
    )
    serialized = response.model_dump(mode="json", by_alias=True)
    assert serialized["data"]["payload"]["occurredAt"].endswith("+08:00")
    assert serialized["data"]["legacyTime"].endswith("+08:00")

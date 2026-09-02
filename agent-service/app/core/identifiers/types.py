"""雪花 ID 的 Pydantic 边界类型。"""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import BeforeValidator, Field, PlainSerializer, WithJsonSchema

_MAX_SIGNED_BIGINT = (1 << 63) - 1
_JSON_SCHEMA = {
    "type": "string",
    "pattern": r"^[1-9][0-9]{0,18}$",
    "description": "十进制字符串形式的 64 位雪花 ID",
}


def _parse_snowflake_id(value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError("雪花 ID 必须是正整数或十进制字符串")  # noqa: TRY004
    if isinstance(value, int):
        parsed = value
    elif (
        isinstance(value, str)
        and value.isascii()
        and value.isdigit()
        and not value.startswith("0")
    ):
        parsed = int(value)
    else:
        raise ValueError("雪花 ID 必须是正整数或十进制字符串")
    if not 0 < parsed <= _MAX_SIGNED_BIGINT:
        raise ValueError("雪花 ID 超出 64 位有符号整数范围")
    return parsed


SnowflakeId = Annotated[
    int,
    BeforeValidator(_parse_snowflake_id),
    Field(gt=0, le=_MAX_SIGNED_BIGINT),
    PlainSerializer(str, return_type=str, when_used="json"),
    WithJsonSchema(_JSON_SCHEMA, mode="validation"),
    WithJsonSchema(_JSON_SCHEMA, mode="serialization"),
]

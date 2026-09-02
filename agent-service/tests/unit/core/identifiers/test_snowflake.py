"""雪花 ID 生成与边界序列化测试。"""

from datetime import UTC, datetime
from unittest import TestCase

from pydantic import BaseModel, ValidationError

from app.core.identifiers import SnowflakeId, SnowflakeIdGenerator

_EPOCH_MILLISECONDS = int(
    datetime(2026, 1, 1, tzinfo=UTC).timestamp() * 1000
)


class _IdentifierPayload(BaseModel):
    id: SnowflakeId


class SnowflakeIdGeneratorTest(TestCase):
    def test_generates_ordered_unique_ids_in_same_millisecond(self) -> None:
        generator = SnowflakeIdGenerator(
            17,
            clock=lambda: _EPOCH_MILLISECONDS + 1000,
        )

        generated = [generator.next_id() for _ in range(10)]

        self.assertEqual(sorted(generated), generated)
        self.assertEqual(len(generated), len(set(generated)))
        self.assertEqual(17, (generated[0] >> 12) & 1023)

    def test_rejects_clock_rollback(self) -> None:
        timestamps = iter(
            [_EPOCH_MILLISECONDS + 2, _EPOCH_MILLISECONDS + 1]
        )
        generator = SnowflakeIdGenerator(0, clock=lambda: next(timestamps))
        generator.next_id()

        with self.assertRaisesRegex(RuntimeError, "系统时钟发生回拨"):
            generator.next_id()

    def test_rejects_invalid_node_id(self) -> None:
        with self.assertRaisesRegex(ValueError, "0 到 1023"):
            SnowflakeIdGenerator(1024)


class SnowflakeIdTypeTest(TestCase):
    def test_accepts_decimal_string_and_serializes_as_string(self) -> None:
        payload = _IdentifierPayload.model_validate({"id": "9007199254740993"})

        self.assertEqual(9007199254740993, payload.id)
        self.assertEqual(
            '{"id":"9007199254740993"}',
            payload.model_dump_json(),
        )

    def test_rejects_non_positive_or_non_decimal_values(self) -> None:
        for value in (0, -1, True, "12.5", ""):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                _IdentifierPayload.model_validate({"id": value})

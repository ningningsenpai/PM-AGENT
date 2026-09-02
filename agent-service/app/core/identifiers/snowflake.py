"""线程安全的 64 位雪花 ID 生成器。"""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import UTC, datetime
from functools import lru_cache
from threading import Lock

from app.core.config import get_settings

_TIMESTAMP_BITS = 41
_NODE_BITS = 10
_SEQUENCE_BITS = 12
_MAX_NODE_ID = (1 << _NODE_BITS) - 1
_MAX_SEQUENCE = (1 << _SEQUENCE_BITS) - 1
_MAX_ELAPSED_MILLISECONDS = (1 << _TIMESTAMP_BITS) - 1
_NODE_SHIFT = _SEQUENCE_BITS
_TIMESTAMP_SHIFT = _NODE_BITS + _SEQUENCE_BITS
_CUSTOM_EPOCH_MILLISECONDS = int(
    datetime(2026, 1, 1, tzinfo=UTC).timestamp() * 1000
)


class SnowflakeIdGenerator:
    """生成 41 位时间戳、10 位节点和 12 位序列组成的正整数 ID。"""

    def __init__(
        self,
        node_id: int,
        *,
        clock: Callable[[], int] | None = None,
        sleeper: Callable[[float], None] | None = None,
    ) -> None:
        if not 0 <= node_id <= _MAX_NODE_ID:
            raise ValueError("雪花算法节点编号必须在 0 到 1023 之间")
        self._node_id = node_id
        self._clock = clock or (lambda: time.time_ns() // 1_000_000)
        self._sleeper = sleeper or time.sleep
        self._lock = Lock()
        self._last_timestamp = -1
        self._sequence = 0

    def next_id(self) -> int:
        """返回新的雪花 ID；检测到时钟回拨时拒绝继续生成。"""
        with self._lock:
            timestamp = self._clock()
            if timestamp < self._last_timestamp:
                raise RuntimeError("系统时钟发生回拨，无法生成雪花 ID")

            if timestamp == self._last_timestamp:
                self._sequence = (self._sequence + 1) & _MAX_SEQUENCE
                if self._sequence == 0:
                    timestamp = self._wait_until_next_millisecond(timestamp)
            else:
                self._sequence = 0

            elapsed = timestamp - _CUSTOM_EPOCH_MILLISECONDS
            if elapsed < 0:
                raise RuntimeError("系统时间早于雪花算法起始时间，无法生成 ID")
            if elapsed > _MAX_ELAPSED_MILLISECONDS:
                raise RuntimeError("雪花算法时间戳位已耗尽，无法生成 ID")

            self._last_timestamp = timestamp
            return (
                (elapsed << _TIMESTAMP_SHIFT)
                | (self._node_id << _NODE_SHIFT)
                | self._sequence
            )

    def _wait_until_next_millisecond(self, timestamp: int) -> int:
        while timestamp <= self._last_timestamp:
            self._sleeper(0.0001)
            timestamp = self._clock()
        return timestamp


@lru_cache
def get_snowflake_id_generator() -> SnowflakeIdGenerator:
    """返回进程内共享的雪花 ID 生成器。"""
    return SnowflakeIdGenerator(get_settings().snowflake.node_id)

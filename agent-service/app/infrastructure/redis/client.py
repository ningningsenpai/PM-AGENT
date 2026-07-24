"""Redis 客户端封装。"""
from __future__ import annotations

from functools import lru_cache

from redis.asyncio import Redis

from app.core.config import get_settings


class RedisProvider:
    def __init__(self, client: Redis, key_prefix: str) -> None:
        self.client = client
        self._key_prefix = key_prefix.rstrip(":")

    def key(self, suffix: str) -> str:
        return f"{self._key_prefix}:{suffix}"


@lru_cache
def get_redis_provider() -> RedisProvider:
    config = get_settings().redis
    client = Redis.from_url(config.url, decode_responses=True)
    return RedisProvider(client, config.key_prefix)

"""可撤销登录会话存储。"""
from __future__ import annotations

from fastapi import Depends

from app.core.logger import get_logger
from app.infrastructure.redis.client import RedisProvider, get_redis_provider

logger = get_logger(__name__)

class SessionStore:
    def __init__(self, redis_provider: RedisProvider) -> None:
        self._redis = redis_provider

    async def create(self, jti: str, user_id: int, ttl_seconds: int) -> None:
        await self._redis.client.set(
            self._redis.key(f"auth:session:{jti}"),
            str(user_id),
            ex=ttl_seconds,
        )

    async def is_active(self, jti: str, user_id: int) -> bool:
        stored = await self._redis.client.get(
            self._redis.key(f"auth:session:{jti}")
        )
        return stored == str(user_id)

    async def revoke(self, jti: str) -> None:
        await self._redis.client.delete(self._redis.key(f"auth:session:{jti}"))


def get_session_store(
    redis_provider: RedisProvider = Depends(get_redis_provider),
) -> SessionStore:
    return SessionStore(redis_provider)

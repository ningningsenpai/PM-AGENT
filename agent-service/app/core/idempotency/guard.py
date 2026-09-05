"""Redis 写请求幂等门禁。"""
from __future__ import annotations

from fastapi import Depends

from app.core.errors import AppException, ErrorCode
from app.infrastructure.redis import RedisProvider, get_redis_provider


class IdempotencyGuard:
    def __init__(self, redis_provider: RedisProvider) -> None:
        self._redis = redis_provider

    async def claim(self, user_id: int, scope: str, key: str | None) -> None:
        """文件上传幂等判断"""
        normalized = (key or "").strip()
        if not normalized:
            raise AppException(ErrorCode.IDEMPOTENCY_KEY_MISSING)
        if len(normalized) > 128:
            raise AppException(ErrorCode.PARAM_INVALID, "幂等键长度不能超过 128 个字符")
        acquired = await self._redis.client.set(
            self._redis.key(f"idempotency:{user_id}:{scope}:{normalized}"),
            "1",
            ex=120,
            nx=True,
        )
        if not acquired:
            raise AppException(ErrorCode.RESOURCE_CONFLICT, "请勿重复提交")


def get_idempotency_guard(
    redis_provider: RedisProvider = Depends(get_redis_provider),
) -> IdempotencyGuard:
    return IdempotencyGuard(redis_provider)

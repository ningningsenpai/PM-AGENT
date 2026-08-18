"""JWT 签发与校验。"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from uuid import uuid4

import jwt

from app.core.config import get_settings
from app.core.errors import AppException, ErrorCode


@dataclass(frozen=True, slots=True)
class IssuedToken:
    value: str
    jti: str
    expires_in: int


@dataclass(frozen=True, slots=True)
class TokenClaims:
    user_id: int
    jti: str


class JwtManager:
    def __init__(self) -> None:
        config = get_settings().security
        self._secret = config.jwt_secret
        self._algorithm = config.jwt_algorithm
        self._ttl_seconds = config.token_ttl_seconds

    def issue(self, user_id: int) -> IssuedToken:
        """ 签发 JWT 令牌。"""
        now = datetime.now(timezone.utc)
        jti = uuid4().hex
        payload = {
            "sub": str(user_id),
            "jti": jti,
            "iat": now,
            "exp": now + timedelta(seconds=self._ttl_seconds),
        }
        value = jwt.encode(payload, self._secret, algorithm=self._algorithm)
        return IssuedToken(value=value, jti=jti, expires_in=self._ttl_seconds)

    def decode(self, token: str) -> TokenClaims:
        """ 解码 JWT 令牌。"""
        try:
            payload = jwt.decode(token, self._secret, algorithms=[self._algorithm])
            user_id = int(payload["sub"])
            jti = str(payload["jti"])
            if user_id <= 0 or not jti:
                raise ValueError("令牌身份字段不合法")
            return TokenClaims(user_id=user_id, jti=jti)
        except (jwt.PyJWTError, KeyError, TypeError, ValueError) as exception:
            raise AppException(ErrorCode.UNAUTHORIZED, "登录状态无效或已过期") from exception


@lru_cache
def get_jwt_manager() -> JwtManager:
    return JwtManager()

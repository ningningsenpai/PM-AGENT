"""FastAPI 当前用户依赖。"""
from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.errors import AppException, ErrorCode
from app.core.security.jwt_manager import JwtManager, get_jwt_manager
from app.infrastructure.redis import SessionStore, get_session_store

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True, slots=True)
class AuthPrincipal:
    user_id: int
    jti: str


async def require_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    jwt_manager: JwtManager = Depends(get_jwt_manager),
    session_store: SessionStore = Depends(get_session_store),
) -> AuthPrincipal:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AppException(ErrorCode.UNAUTHORIZED)
    claims = jwt_manager.decode(credentials.credentials)
    if not await session_store.is_active(claims.jti, claims.user_id):
        raise AppException(ErrorCode.UNAUTHORIZED, "登录状态已失效")
    return AuthPrincipal(user_id=claims.user_id, jti=claims.jti)

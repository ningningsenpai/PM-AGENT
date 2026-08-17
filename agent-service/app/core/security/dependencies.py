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
    """当前认证用户主体。包含user_id 和 jti（签发token唯一标识）。"""
    user_id: int
    jti: str


async def require_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    jwt_manager: JwtManager = Depends(get_jwt_manager),
    session_store: SessionStore = Depends(get_session_store),
) -> AuthPrincipal:
    """从请求头解析并校验 Bearer JWT，返回当前登录用户主体。

    Args:
        credentials: 请求头中的 HTTP Authorization 凭证；由 FastAPI 注入。
        jwt_manager: JWT 签发与校验管理器；由 FastAPI 注入。
        session_store: Redis 会话存储；由 FastAPI 注入。

    Returns:
        AuthPrincipal: 当前认证用户主体，包含 user_id 和 jti。

    Raises:
        AppException: 凭证缺失或格式错误、JWT 解析失败、会话已失效时抛出 UNAUTHORIZED。
    """
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AppException(ErrorCode.UNAUTHORIZED)
    claims = jwt_manager.decode(credentials.credentials)
    if not await session_store.is_active(claims.jti, claims.user_id):
        raise AppException(ErrorCode.UNAUTHORIZED, "登录状态已失效")
    return AuthPrincipal(user_id=claims.user_id, jti=claims.jti)

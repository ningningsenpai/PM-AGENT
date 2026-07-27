"""注册、登录与注销编排。"""
from __future__ import annotations

from datetime import datetime

from app.core.logger import get_logger
from app.core.security import AuthPrincipal, JwtManager
from app.infrastructure.redis import SessionStore
from app.modules.auth.schemas import LoginRequest, LoginResponse, RegisterRequest
from app.modules.user.schemas import to_profile
from app.modules.user.service import UserService

logger = get_logger(__name__)

class AuthService:
    def __init__(
        self,
        users: UserService,
        jwt_manager: JwtManager,
        sessions: SessionStore,
    ) -> None:
        self._users = users
        self._jwt = jwt_manager
        self._sessions = sessions

    async def register(self, request: RegisterRequest) -> LoginResponse:
        logger.info("用户注册：%s", request.email)
        user = await self._users.register(
            request.username,
            request.email,
            request.password,
            datetime.now(),
        )
        logger.info("用户注册成功：%s， 用户ID：%s", user.id, user.email)
        return await self._create_login_response(user)

    async def login(self, request: LoginRequest) -> LoginResponse:
        logger.info("用户登录：%s", request.email)
        user = await self._users.authenticate(request.email, request.password)
        logger.info("用户：%s 登录成功， 用户ID：%s", user.email, user.id)
        return await self._create_login_response(user)

    async def logout(self, principal: AuthPrincipal) -> None:
        await self._sessions.revoke(principal.jti)
        logger.info("用户：%s JWT Token 注销成功", principal.user_id)

    async def _create_login_response(self, user) -> LoginResponse:
        token = self._jwt.issue(user.id)
        await self._sessions.create(token.jti, user.id, token.expires_in)
        logger.info("用户：%s JWT Token 下发成功", user.id)
        return LoginResponse(
            token_name="Authorization",
            token_value=token.value,
            user=to_profile(user),
        )

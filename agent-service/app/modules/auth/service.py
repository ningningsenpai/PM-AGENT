"""注册、登录与注销编排。"""
from __future__ import annotations

from datetime import datetime

from app.core.security import JwtManager
from app.infrastructure.redis import SessionStore
from app.modules.auth.schemas import LoginRequest, LoginResponse, RegisterRequest
from app.modules.user.schemas import to_profile
from app.modules.user.service import UserService


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
        user = await self._users.register(
            request.username,
            request.email,
            request.password,
            datetime.now(),
        )
        return await self._create_login_response(user)

    async def login(self, request: LoginRequest) -> LoginResponse:
        user = await self._users.authenticate(request.email, request.password)
        return await self._create_login_response(user)

    async def logout(self, jti: str) -> None:
        await self._sessions.revoke(jti)

    async def _create_login_response(self, user) -> LoginResponse:
        token = self._jwt.issue(user.id)
        await self._sessions.create(token.jti, user.id, token.expires_in)
        return LoginResponse(
            token_name="Authorization",
            token_value=token.value,
            user=to_profile(user),
        )

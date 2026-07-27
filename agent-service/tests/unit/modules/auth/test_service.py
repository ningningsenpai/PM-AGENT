"""认证业务服务单元测试。"""

from __future__ import annotations

from datetime import datetime
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock, patch

from app.core.security import AuthPrincipal
from app.core.security.jwt_manager import IssuedToken
from app.modules.auth import service as auth_service_module
from app.modules.auth.schemas import LoginRequest, LoginResponse, RegisterRequest
from app.modules.auth.service import AuthService
from app.modules.user.models import User
from app.modules.user.schemas import to_profile


def _user() -> User:
    user = User(
        username="tester",
        email="tester@example.com",
        password_hash="hashed-password",
        status="enabled",
        last_login_at=datetime(2026, 7, 27, 10, 0, 0),
    )
    user.id = 7
    user.created_at = datetime(2026, 7, 27, 9, 0, 0)
    user.updated_at = datetime(2026, 7, 27, 9, 0, 0)
    return user


def _login_response(user: User) -> LoginResponse:
    return LoginResponse(
        token_name="Authorization",
        token_value="issued-token",
        user=to_profile(user),
    )


class AuthServiceTest(IsolatedAsyncioTestCase):
    async def test_register_delegates_user_creation(self) -> None:
        """验证注册会委托 User Service 创建用户。

        @Param request: 包含合法用户名、邮箱和密码的 RegisterRequest。
        @Return: User Service 创建用户后生成的 LoginResponse。
        @SideEffect: 调用 User Service 注册方法并进入认证结果创建流程。
        """
        user = _user()
        users = AsyncMock()
        users.register.return_value = user
        service = AuthService(users, Mock(), AsyncMock())
        expected = _login_response(user)
        service._create_login_response = AsyncMock(return_value=expected)
        request = RegisterRequest(
            username="Tester",
            email="tester@example.com",
            password="secret1",
        )

        result = await service.register(request)

        register_args = users.register.await_args.args
        self.assertEqual(("Tester", "tester@example.com", "secret1"), register_args[:3])
        self.assertIsInstance(register_args[3], datetime)
        service._create_login_response.assert_awaited_once_with(user)
        self.assertEqual(expected, result)

    async def test_login_issues_token_and_creates_session(self) -> None:
        """验证合法用户登录后返回认证结果。

        @Param request: 包含合法邮箱和密码的 LoginRequest。
        @Return: 包含令牌和用户资料的 LoginResponse。
        @SideEffect: 签发 JWT，并创建具有正确有效期的 Redis 会话。
        """
        user = _user()
        users = AsyncMock()
        users.authenticate.return_value = user
        jwt_manager = Mock()
        jwt_manager.issue.return_value = IssuedToken(
            value="issued-token",
            jti="session-jti",
            expires_in=3600,
        )
        sessions = AsyncMock()
        service = AuthService(users, jwt_manager, sessions)
        request = LoginRequest(
            email="tester@example.com",
            password="secret1",
        )

        result = await service.login(request)

        users.authenticate.assert_awaited_once_with(
            "tester@example.com",
            "secret1",
        )
        jwt_manager.issue.assert_called_once_with(7)
        sessions.create.assert_awaited_once_with("session-jti", 7, 3600)
        self.assertEqual("Authorization", result.token_name)
        self.assertEqual("issued-token", result.token_value)
        self.assertEqual(7, result.user.id)

    async def test_logout_revokes_current_session(self) -> None:
        """验证注销会撤销当前登录会话。

        @Param principal: 包含用户 ID 和会话 JTI 的 AuthPrincipal。
        @Return: None，操作成功完成。
        @SideEffect: 调用 SessionStore 撤销当前 JTI。
        """
        sessions = AsyncMock()
        service = AuthService(AsyncMock(), Mock(), sessions)
        principal = AuthPrincipal(user_id=7, jti="session-jti")

        await service.logout(principal)

        sessions.revoke.assert_awaited_once_with("session-jti")

    async def test_login_log_does_not_expose_credentials(self) -> None:
        """验证登录日志不会泄露密码、令牌或完整 JTI。

        @Param request: 包含敏感密码的合法 LoginRequest。
        @Return: 包含认证结果的 LoginResponse，日志中不包含敏感值。
        @SideEffect: 记录登录过程日志并创建 Redis 会话。
        """
        user = _user()
        users = AsyncMock()
        users.authenticate.return_value = user
        jwt_manager = Mock()
        jwt_manager.issue.return_value = IssuedToken(
            value="sensitive-token",
            jti="sensitive-jti",
            expires_in=3600,
        )
        sessions = AsyncMock()
        service = AuthService(users, jwt_manager, sessions)
        request = LoginRequest(
            email="tester@example.com",
            password="sensitive-password",
        )

        with patch.object(auth_service_module, "logger") as logger:
            await service.login(request)

        calls = repr(logger.method_calls)
        self.assertNotIn("sensitive-password", calls)
        self.assertNotIn("sensitive-token", calls)
        self.assertNotIn("sensitive-jti", calls)

"""用户业务服务单元测试。"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock, patch

from sqlalchemy.exc import IntegrityError

from app.core.errors import AppException, ErrorCode
from app.modules.user import service as user_service_module
from app.modules.user.models import User
from app.modules.user.schemas import (
    ChangePasswordRequest,
    UpdateUserProfileRequest,
)
from app.modules.user.service import UserService


def _user(
    *,
    user_id: int = 7,
    username: str = "tester",
    email: str = "tester@example.com",
    status: str = "enabled",
) -> User:
    user = User(
        username=username,
        email=email,
        password_hash="hashed-password",
        status=status,
        last_login_at=datetime(2026, 7, 27, 10, 0, 0),
    )
    user.id = user_id
    user.created_at = datetime(2026, 7, 27, 9, 0, 0)
    user.updated_at = datetime(2026, 7, 27, 9, 0, 0)
    return user


def _repository(**overrides):
    defaults = {
        "session": SimpleNamespace(
            commit=AsyncMock(),
            rollback=AsyncMock(),
        ),
        "get_by_id": AsyncMock(return_value=None),
        "get_by_email": AsyncMock(return_value=None),
        "get_by_username": AsyncMock(return_value=None),
        "add": AsyncMock(),
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class UserServiceTest(IsolatedAsyncioTestCase):
    async def test_register_normalizes_and_persists_user(self) -> None:
        """验证注册会规范化身份字段并持久化启用用户。

        @Param username: 包含首尾空格和大写字符的用户名。
        @Param email: 包含首尾空格和大写字符的邮箱。
        @Param password: 待哈希的注册密码。
        @Param last_login_at: 注册后的初始登录时间。
        @Return: 已规范化且状态为 enabled 的 User。
        @SideEffect: 哈希密码、添加用户并提交数据库事务。
        """
        repository = _repository()

        async def assign_id(user: User) -> User:
            user.id = 7
            return user

        repository.add.side_effect = assign_id
        passwords = Mock()
        passwords.hash.return_value = "hashed-secret"
        service = UserService(repository, passwords)
        last_login_at = datetime(2026, 7, 27, 10, 0, 0)

        with patch.object(user_service_module, "logger") as logger:
            result = await service.register(
                "  Tester  ",
                "  TESTER@Example.COM  ",
                "sensitive-password",
                last_login_at,
            )

        self.assertEqual("tester", result.username)
        self.assertEqual("tester@example.com", result.email)
        self.assertEqual("hashed-secret", result.password_hash)
        self.assertEqual("enabled", result.status)
        passwords.hash.assert_called_once_with("sensitive-password")
        repository.add.assert_awaited_once_with(result)
        repository.session.commit.assert_awaited_once()
        self.assertIn("action=user.create", repr(logger.method_calls))
        self.assertNotIn("sensitive-password", repr(logger.method_calls))

    async def test_register_rejects_duplicate_identity(self) -> None:
        """验证用户名或邮箱已存在时拒绝注册。

        @Param username: 可能与已有用户冲突的用户名。
        @Param email: 可能与已有用户冲突的邮箱。
        @Param password: 合法注册密码。
        @Param last_login_at: 注册请求的初始登录时间。
        @Return: 分别抛出 USERNAME_EXISTS 或 EMAIL_EXISTS 的 AppException。
        """
        cases = [
            (
                _repository(get_by_username=AsyncMock(return_value=_user())),
                ErrorCode.USERNAME_EXISTS,
            ),
            (
                _repository(get_by_email=AsyncMock(return_value=_user())),
                ErrorCode.EMAIL_EXISTS,
            ),
        ]

        for repository, expected_error in cases:
            with self.subTest(error=expected_error):
                service = UserService(repository, Mock())
                with self.assertRaises(AppException) as caught:
                    await service.register(
                        "tester",
                        "tester@example.com",
                        "secret-password",
                        datetime.now(),
                    )
                self.assertIs(expected_error, caught.exception.error)
                repository.add.assert_not_awaited()

    async def test_register_wraps_database_conflict(self) -> None:
        """验证数据库唯一约束冲突会回滚并转换为业务异常。

        @Param username: 尚未被预查询发现冲突的用户名。
        @Param email: 尚未被预查询发现冲突的邮箱。
        @Param password: 合法注册密码。
        @Param last_login_at: 注册请求的初始登录时间。
        @Return: 抛出 RESOURCE_CONFLICT 的 AppException。
        @SideEffect: 回滚数据库事务。
        """
        repository = _repository(
            add=AsyncMock(
                side_effect=IntegrityError("insert", {}, RuntimeError("duplicate"))
            )
        )
        passwords = Mock()
        passwords.hash.return_value = "hashed-secret"
        service = UserService(repository, passwords)

        with self.assertRaises(AppException) as caught:
            await service.register(
                "tester",
                "tester@example.com",
                "secret-password",
                datetime.now(),
            )

        self.assertIs(ErrorCode.RESOURCE_CONFLICT, caught.exception.error)
        repository.session.rollback.assert_awaited_once()

    async def test_authenticate_updates_last_login(self) -> None:
        """验证正确凭据能够完成用户认证。

        @Param email: 已注册且启用用户的邮箱。
        @Param password: 与密码哈希匹配的明文密码。
        @Return: 更新最后登录时间后的 User。
        @SideEffect: 校验密码并提交最后登录时间。
        """
        user = _user()
        repository = _repository(get_by_email=AsyncMock(return_value=user))
        passwords = Mock()
        passwords.verify.return_value = True
        service = UserService(repository, passwords)
        previous_login = user.last_login_at

        result = await service.authenticate("TESTER@example.com", "secret-password")

        self.assertIs(user, result)
        self.assertGreater(result.last_login_at, previous_login)
        passwords.verify.assert_called_once_with(
            "secret-password",
            "hashed-password",
        )
        repository.session.commit.assert_awaited_once()

    async def test_authenticate_rejects_invalid_credentials(self) -> None:
        """验证用户不存在或密码错误时返回相同登录错误。

        @Param email: 不存在用户或已有用户的邮箱。
        @Param password: 任意密码或不匹配的密码。
        @Return: 抛出 AUTH_LOGIN_FAILED 的 AppException。
        """
        cases = [
            (_repository(), Mock()),
            (
                _repository(get_by_email=AsyncMock(return_value=_user())),
                Mock(verify=Mock(return_value=False)),
            ),
        ]

        for repository, passwords in cases:
            with self.subTest(user_exists=repository.get_by_email.return_value is not None):
                service = UserService(repository, passwords)
                with self.assertRaises(AppException) as caught:
                    await service.authenticate(
                        "tester@example.com",
                        "wrong-password",
                    )
                self.assertIs(ErrorCode.AUTH_LOGIN_FAILED, caught.exception.error)
                repository.session.commit.assert_not_awaited()

    async def test_authenticate_rejects_disabled_user(self) -> None:
        """验证禁用用户不能通过认证。

        @Param email: 状态为 disabled 的用户邮箱。
        @Param password: 与密码哈希匹配的明文密码。
        @Return: 抛出 USER_DISABLED 的 AppException。
        """
        repository = _repository(
            get_by_email=AsyncMock(return_value=_user(status="disabled"))
        )
        passwords = Mock()
        passwords.verify.return_value = True
        service = UserService(repository, passwords)

        with self.assertRaises(AppException) as caught:
            await service.authenticate("tester@example.com", "secret-password")

        self.assertIs(ErrorCode.USER_DISABLED, caught.exception.error)
        repository.session.commit.assert_not_awaited()

    async def test_get_profile_returns_existing_user(self) -> None:
        """验证资料查询返回用户公开资料。

        @Param user_id: 已存在用户的 ID。
        @Return: 对应用户的 UserProfileResponse。
        """
        repository = _repository(get_by_id=AsyncMock(return_value=_user()))
        service = UserService(repository, Mock())

        result = await service.get_profile(7)

        self.assertEqual(7, result.id)
        self.assertEqual("tester@example.com", result.email)

    async def test_get_profile_rejects_missing_user(self) -> None:
        """验证资料查询拒绝不存在的用户。

        @Param user_id: 数据库中不存在的用户 ID。
        @Return: 抛出 USER_NOT_FOUND 的 AppException。
        """
        service = UserService(_repository(), Mock())

        with self.assertRaises(AppException) as caught:
            await service.get_profile(404)

        self.assertIs(ErrorCode.USER_NOT_FOUND, caught.exception.error)

    async def test_update_profile_persists_normalized_identity(self) -> None:
        """验证资料修改会保存规范化后的用户名和邮箱。

        @Param user_id: 已存在用户的 ID。
        @Param request: 包含新用户名和邮箱的 UpdateUserProfileRequest。
        @Return: 包含新身份字段的 UserProfileResponse。
        @SideEffect: 更新用户实体并提交数据库事务。
        """
        user = _user()
        repository = _repository(get_by_id=AsyncMock(return_value=user))
        service = UserService(repository, Mock())
        request = UpdateUserProfileRequest(
            username="NewName",
            email="NEW@example.com",
        )

        result = await service.update_profile(7, request)

        self.assertEqual("newname", result.username)
        self.assertEqual("new@example.com", result.email)
        repository.session.commit.assert_awaited_once()

    async def test_update_profile_rejects_identity_conflict(self) -> None:
        """验证资料修改拒绝被其他用户占用的身份字段。

        @Param user_id: 当前用户 ID。
        @Param request: 包含冲突用户名或邮箱的资料修改请求。
        @Return: 分别抛出 USERNAME_EXISTS 或 EMAIL_EXISTS 的 AppException。
        """
        cases = [
            (
                _repository(
                    get_by_id=AsyncMock(return_value=_user()),
                    get_by_username=AsyncMock(return_value=_user(user_id=8)),
                ),
                ErrorCode.USERNAME_EXISTS,
            ),
            (
                _repository(
                    get_by_id=AsyncMock(return_value=_user()),
                    get_by_email=AsyncMock(return_value=_user(user_id=8)),
                ),
                ErrorCode.EMAIL_EXISTS,
            ),
        ]
        request = UpdateUserProfileRequest(
            username="other",
            email="other@example.com",
        )

        for repository, expected_error in cases:
            with self.subTest(error=expected_error):
                service = UserService(repository, Mock())
                with self.assertRaises(AppException) as caught:
                    await service.update_profile(7, request)
                self.assertIs(expected_error, caught.exception.error)
                repository.session.commit.assert_not_awaited()

    async def test_update_profile_rolls_back_database_conflict(self) -> None:
        """验证资料提交发生唯一约束冲突时回滚事务。

        @Param user_id: 已存在用户的 ID。
        @Param request: 预查询未发现冲突的资料修改请求。
        @Return: 抛出 RESOURCE_CONFLICT 的 AppException。
        @SideEffect: 回滚数据库事务。
        """
        user = _user()
        session = SimpleNamespace(
            commit=AsyncMock(
                side_effect=IntegrityError("update", {}, RuntimeError("duplicate"))
            ),
            rollback=AsyncMock(),
        )
        repository = _repository(
            session=session,
            get_by_id=AsyncMock(return_value=user),
        )
        service = UserService(repository, Mock())
        request = UpdateUserProfileRequest(
            username="other",
            email="other@example.com",
        )

        with self.assertRaises(AppException) as caught:
            await service.update_profile(7, request)

        self.assertIs(ErrorCode.RESOURCE_CONFLICT, caught.exception.error)
        session.rollback.assert_awaited_once()

    async def test_change_password_hashes_and_commits_new_password(self) -> None:
        """验证原密码正确时保存新密码哈希。

        @Param user_id: 已存在用户的 ID。
        @Param request: 原密码正确且两次新密码一致的 ChangePasswordRequest。
        @Return: None，操作成功完成。
        @SideEffect: 生成新密码哈希并提交数据库事务。
        """
        user = _user()
        repository = _repository(get_by_id=AsyncMock(return_value=user))
        passwords = Mock()
        passwords.verify.return_value = True
        passwords.hash.return_value = "new-hash"
        service = UserService(repository, passwords)
        request = ChangePasswordRequest(
            old_password="old-password",
            new_password="new-password",
            confirm_password="new-password",
        )

        await service.change_password(7, request)

        self.assertEqual("new-hash", user.password_hash)
        passwords.hash.assert_called_once_with("new-password")
        repository.session.commit.assert_awaited_once()

    async def test_change_password_rejects_invalid_old_password(self) -> None:
        """验证原密码错误时拒绝修改密码。

        @Param user_id: 已存在用户的 ID。
        @Param request: 原密码错误且新密码合法的 ChangePasswordRequest。
        @Return: 抛出 PASSWORD_INVALID 的 AppException。
        """
        repository = _repository(get_by_id=AsyncMock(return_value=_user()))
        passwords = Mock()
        passwords.verify.return_value = False
        service = UserService(repository, passwords)
        request = ChangePasswordRequest(
            old_password="wrong-password",
            new_password="new-password",
            confirm_password="new-password",
        )

        with self.assertRaises(AppException) as caught:
            await service.change_password(7, request)

        self.assertIs(ErrorCode.PASSWORD_INVALID, caught.exception.error)
        passwords.hash.assert_not_called()
        repository.session.commit.assert_not_awaited()

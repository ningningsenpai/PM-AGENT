"""用户业务服务。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy.exc import IntegrityError

from app.core.errors import AppException, ErrorCode
from app.core.logger import get_logger
from app.core.security import PasswordManager
from app.modules.user.domain import UserStatus
from app.modules.user.errors import email_exists, user_not_found, username_exists
from app.modules.user.models import User
from app.modules.user.repository import UserRepository
from app.modules.user.schemas import (
    ChangePasswordRequest,
    UpdateUserProfileRequest,
    UserProfileResponse,
    to_profile,
)

logger = get_logger(__name__)


class UserService:
    def __init__(
        self,
        repository: UserRepository,
        password_manager: PasswordManager,
    ) -> None:
        self._repository = repository
        self._passwords = password_manager

    async def register(
        self,
        username: str,
        email: str,
        password: str,
        last_login_at: datetime,
    ) -> User:
        normalized_username = username.strip().lower()
        normalized_email = email.strip().lower()
        await self._validate_unique(None, normalized_username, normalized_email)
        user = User(
            username=normalized_username,
            email=normalized_email,
            password_hash=self._passwords.hash(password),
            status=UserStatus.ENABLED.value,
            last_login_at=last_login_at,
        )
        try:
            await self._repository.add(user)
            await self._repository.session.commit()
        except IntegrityError as exception:
            await self._repository.session.rollback()
            logger.exception("用户创建失败 action=user.create")
            raise AppException(
                ErrorCode.RESOURCE_CONFLICT,
                "用户名或邮箱已存在",
            ) from exception
        logger.info("用户创建成功 action=user.create userId=%s", user.id)
        return user

    async def authenticate(self, email: str, password: str) -> User:
        logger.debug("用户认证开始 action=user.authenticate")
        user = await self._repository.get_by_email(email.strip().lower())
        if user is None or not self._passwords.verify(password, user.password_hash):
            raise AppException(ErrorCode.AUTH_LOGIN_FAILED)
        if user.status != UserStatus.ENABLED.value:
            raise AppException(ErrorCode.USER_DISABLED)
        user.last_login_at = datetime.now()
        await self._repository.session.commit()
        logger.debug(
            "用户认证完成 action=user.authenticate userId=%s",
            user.id,
        )
        return user

    async def get_profile(self, user_id: int) -> UserProfileResponse:
        logger.debug("查询用户资料 action=user.profile.get userId=%s", user_id)
        profile = to_profile(await self.require_user(user_id))
        logger.debug(
            "用户资料查询完成 action=user.profile.get userId=%s",
            user_id,
        )
        return profile

    async def update_profile(
        self,
        user_id: int,
        request: UpdateUserProfileRequest,
    ) -> UserProfileResponse:
        logger.info("修改用户资料 action=user.profile.update userId=%s", user_id)
        user = await self.require_user(user_id)
        username = request.username.strip().lower()
        email = request.email.strip().lower()
        await self._validate_unique(user.id, username, email)
        user.username = username
        user.email = email
        try:
            await self._repository.session.commit()
        except IntegrityError as exception:
            await self._repository.session.rollback()
            logger.exception(
                "用户资料修改失败 action=user.profile.update userId=%s",
                user_id,
            )
            raise AppException(
                ErrorCode.RESOURCE_CONFLICT,
                "用户名或邮箱已存在",
            ) from exception
        logger.info(
            "用户资料修改成功 action=user.profile.update userId=%s",
            user_id,
        )
        return to_profile(user)

    async def change_password(
        self,
        user_id: int,
        request: ChangePasswordRequest,
    ) -> None:
        logger.info("修改用户密码 action=user.password.change userId=%s", user_id)
        user = await self.require_user(user_id)
        if not self._passwords.verify(request.old_password, user.password_hash):
            raise AppException(ErrorCode.PASSWORD_INVALID)
        user.password_hash = self._passwords.hash(request.new_password)
        await self._repository.session.commit()
        logger.info(
            "用户密码修改成功 action=user.password.change userId=%s",
            user_id,
        )

    async def require_user(self, user_id: int) -> User:
        user = await self._repository.get_by_id(user_id)
        if user is None:
            raise user_not_found()
        return user

    async def _validate_unique(
        self,
        current_user_id: int | None,
        username: str,
        email: str,
    ) -> None:
        username_user = await self._repository.get_by_username(username)
        if username_user is not None and username_user.id != current_user_id:
            raise username_exists()
        email_user = await self._repository.get_by_email(email)
        if email_user is not None and email_user.id != current_user_id:
            raise email_exists()

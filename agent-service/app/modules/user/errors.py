"""用户模块异常工厂。"""
from app.core.errors import AppException, ErrorCode


def user_not_found() -> AppException:
    return AppException(ErrorCode.USER_NOT_FOUND)


def username_exists() -> AppException:
    return AppException(ErrorCode.USERNAME_EXISTS)


def email_exists() -> AppException:
    return AppException(ErrorCode.EMAIL_EXISTS)

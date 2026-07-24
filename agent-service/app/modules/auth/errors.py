"""认证模块异常工厂。"""
from app.core.errors import AppException, ErrorCode


def login_failed() -> AppException:
    return AppException(ErrorCode.AUTH_LOGIN_FAILED)

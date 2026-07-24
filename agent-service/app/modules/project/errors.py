"""项目模块异常工厂。"""
from app.core.errors import AppException, ErrorCode


def project_not_found() -> AppException:
    return AppException(ErrorCode.PROJECT_NOT_FOUND)


def project_disabled() -> AppException:
    return AppException(ErrorCode.PROJECT_DISABLED)


def project_name_exists() -> AppException:
    return AppException(ErrorCode.PROJECT_NAME_EXISTS)

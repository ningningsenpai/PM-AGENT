"""项目文件异常工厂。"""
from app.core.errors import AppException, ErrorCode


def file_not_found() -> AppException:
    return AppException(ErrorCode.FILE_NOT_FOUND)


def file_busy() -> AppException:
    return AppException(ErrorCode.FILE_BUSY)


def file_status_invalid() -> AppException:
    return AppException(ErrorCode.FILE_STATUS_INVALID)

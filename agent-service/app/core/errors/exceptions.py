"""业务异常定义。"""
from __future__ import annotations

from app.core.errors.codes import ErrorCode


class AppException(RuntimeError):
    """携带稳定业务错误码的异常。"""

    def __init__(self, error: ErrorCode, message: str | None = None) -> None:
        self.error = error
        self.message = message or error.message
        super().__init__(self.message)

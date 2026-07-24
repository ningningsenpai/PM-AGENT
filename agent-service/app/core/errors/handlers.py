"""FastAPI 全局异常处理。"""
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.errors.codes import ErrorCode
from app.core.errors.exceptions import AppException
from app.core.response import failure

logger = logging.getLogger(__name__)


def _body(code: int, message: str) -> dict:
    return failure(code, message).model_dump(mode="json")


def install_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppException)
    async def handle_app_exception(_request, exception: AppException):
        logger.warning(
            "业务异常 code=%s message=%s",
            exception.error.code,
            exception.message,
        )
        return JSONResponse(
            status_code=200,
            content=_body(exception.error.code, exception.message),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_request, exception: RequestValidationError):
        first = exception.errors()[0] if exception.errors() else None
        message = "参数不合法"
        if first:
            location = ".".join(str(item) for item in first.get("loc", ()) if item != "body")
            detail_by_type = {
                "missing": "字段不能为空",
                "string_too_short": "字段长度不足",
                "string_too_long": "字段长度超出限制",
                "greater_than_equal": "字段值小于允许范围",
                "less_than_equal": "字段值大于允许范围",
                "int_parsing": "字段必须是整数",
                "bool_parsing": "字段必须是布尔值",
                "value_error": str(
                    first.get("ctx", {}).get("error", "字段值不合法")
                ).removeprefix("Value error, "),
            }
            detail = detail_by_type.get(first.get("type"), "字段值不合法")
            message = f"{location}：{detail}" if location else str(detail)
        return JSONResponse(
            status_code=200,
            content=_body(ErrorCode.PARAM_INVALID.code, message),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(_request, exception: Exception):
        logger.exception("未处理的系统异常", exc_info=exception)
        return JSONResponse(
            status_code=500,
            content=_body(ErrorCode.SYSTEM_ERROR.code, ErrorCode.SYSTEM_ERROR.message),
        )

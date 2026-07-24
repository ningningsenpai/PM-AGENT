"""统一 API 响应模型。"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from app.core.trace import get_trace_id


class ApiResponse(BaseModel):
    """与原 Java `R<T>` 保持一致的响应结构。"""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    code: int = 0
    message: str = "成功"
    data: Any = None
    traceId: str


def success(data: Any = None) -> ApiResponse:
    return ApiResponse(data=data, traceId=get_trace_id())


def failure(code: int, message: str) -> ApiResponse:
    return ApiResponse(code=code, message=message, data=None, traceId=get_trace_id())

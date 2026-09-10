"""统一 API 响应模型。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, field_serializer

from app.core.time import shanghai_iso
from app.core.trace import get_trace_id


class ApiResponse(BaseModel):
    """与原 Java `R<T>` 保持一致的响应结构。"""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    code: int = 200
    message: str = "成功"
    data: Any = None
    traceId: str

    @field_serializer("data", when_used="json")
    def serialize_data(self, value):
        """确保无显式响应模型的嵌套时间也统一携带上海时区。"""

        def convert(item):
            if isinstance(item, datetime):
                return shanghai_iso(item)
            if isinstance(item, BaseModel):
                return item.model_dump(mode="json", by_alias=True)
            if isinstance(item, dict):
                return {key: convert(child) for key, child in item.items()}
            if isinstance(item, list):
                return [convert(child) for child in item]
            if isinstance(item, tuple):
                return tuple(convert(child) for child in item)
            return item

        return convert(value)


def success(data: Any = None) -> ApiResponse:
    return ApiResponse(data=data, traceId=get_trace_id())


def failure(code: int, message: str) -> ApiResponse:
    return ApiResponse(code=code, message=message, data=None, traceId=get_trace_id())

"""FastAPI 中间件。"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from uuid import uuid4

from fastapi import Request, Response

from app.core.request_context import RequestContext, reset_request_context, set_request_context

__all__ = ["request_context_middleware"]


async def request_context_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """统一接收请求头并写入异步上下文。"""
    trace_id = request.headers.get("X-Trace-Id") or uuid4().hex
    token = set_request_context(
        RequestContext(
            trace_id=trace_id,
            user_id=request.headers.get("X-User-Id"),
            tenant_id=request.headers.get("X-Tenant-Id"),
        )
    )

    try:
        response = await call_next(request)
        response.headers["X-Trace-Id"] = trace_id
        return response
    finally:
        reset_request_context(token)

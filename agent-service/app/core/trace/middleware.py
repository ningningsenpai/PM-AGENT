"""traceId 生成与透传中间件。"""
from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware

from app.core.trace.context import get_trace_id, reset_trace_id, set_trace_id


class TraceMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        token = set_trace_id(request.headers.get("X-Trace-Id"))
        request.state.trace_id = get_trace_id()
        try:
            response = await call_next(request)
            response.headers["X-Trace-Id"] = request.state.trace_id
            return response
        finally:
            reset_trace_id(token)

"""请求上下文管理。"""
from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass

__all__ = [
    "RequestContext",
    "get_request_context",
    "reset_request_context",
    "set_request_context",
]


@dataclass(frozen=True)
class RequestContext:
    """RequestContext 保存单次请求的链路与身份信息。"""

    trace_id: str
    user_id: str | None = None
    tenant_id: str | None = None


_request_context: ContextVar[RequestContext | None] = ContextVar(
    "request_context",
    default=None,
)


def set_request_context(context: RequestContext) -> Token[RequestContext | None]:
    """写入当前协程请求上下文，并返回可用于恢复的 token。"""
    return _request_context.set(context)


def reset_request_context(token: Token[RequestContext | None]) -> None:
    """请求结束后恢复上下文，避免异步请求之间串值。"""
    _request_context.reset(token)


def get_request_context() -> RequestContext:
    """获取当前请求上下文；仅允许在 FastAPI 请求链路内调用。"""
    context = _request_context.get()
    if context is None:
        raise RuntimeError("当前请求上下文不存在")
    return context

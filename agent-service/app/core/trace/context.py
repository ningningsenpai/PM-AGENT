"""traceId 上下文。"""
from __future__ import annotations

from contextvars import ContextVar, Token
from uuid import uuid4

_trace_id: ContextVar[str] = ContextVar("pm_agent_trace_id", default="")


def set_trace_id(value: str | None) -> Token:
    normalized = (value or "").strip()[:128]
    return _trace_id.set(normalized or uuid4().hex)


def reset_trace_id(token: Token) -> None:
    _trace_id.reset(token)


def get_trace_id() -> str:
    current = _trace_id.get()
    if current:
        return current
    generated = uuid4().hex
    _trace_id.set(generated)
    return generated

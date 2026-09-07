"""模型调用预算、可恢复的测试费用账本和请求级轨迹。"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import sqlite3
import time
from uuid import uuid4

_events: ContextVar[list | None] = ContextVar("llm_events", default=None)


@contextmanager
def capture_calls(events: list):
    token = _events.set(events)
    try:
        yield
    finally:
        _events.reset(token)


def input_upper_bound(body: dict) -> int:
    """按序列化字节数保守预留输入，另留协议开销，不混用历史累计 usage。"""
    return len(json.dumps(body, ensure_ascii=False).encode("utf-8")) + 1024


def safe_payload(value):
    if isinstance(value, dict):
        return {k: ("[已隐藏]" if k.lower() in {
            "authorization", "api_key", "password", "secret", "access_token",
        } else safe_payload(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [safe_payload(v) for v in value]
    if isinstance(value, str):
        key = os.getenv("DEEPSEEK_API_KEY", "")
        if key:
            value = value.replace(key, "[已隐藏]")
    return value


def record_tool(step, result):
    """记录工具完整结果，失败也保留调用关联与耗时。"""
    if _events.get() is not None:
        _events.get().append({"type": "tool", "step": step, **safe_payload(result.model_dump(mode="json"))})


class ModelCall:
    """先持久化预算预留，再发请求；未知用量保留预留，避免按零费用计算。"""

    def __init__(self, body: dict, context_limit: int | None):
        self.id = uuid4().hex
        self.started = time.perf_counter()
        upper = input_upper_bound(body)
        if context_limit and upper + body["max_tokens"] > context_limit:
            raise ValueError("本次模型输入与输出预留超过上下文预算，请缩小批次或历史范围")
        self.reserved = (upper * 3 + body["max_tokens"] * 9) / 1_000_000
        self.ledger = os.getenv("PM_AGENT_TEST_BUDGET_PATH", "")
        if self.ledger:
            if body["model"] != "deepseek-v4-flash":
                raise ValueError("测试费用账本当前仅允许已定价的 deepseek-v4-flash")
            Path(self.ledger).parent.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(self.ledger, timeout=30) as conn:
                conn.execute("CREATE TABLE IF NOT EXISTS calls (id TEXT PRIMARY KEY, reserved REAL, charged REAL, state TEXT)")
                conn.execute("BEGIN IMMEDIATE")
                used = conn.execute("SELECT COALESCE(SUM(charged),0) FROM calls").fetchone()[0]
                if used + self.reserved > float(os.getenv("PM_AGENT_TEST_BUDGET_CNY", "30")):
                    raise ValueError("本次测试的模型费用预留超过累计预算，已停止新的付费请求")
                conn.execute("INSERT INTO calls VALUES (?,?,?,?)", (self.id, self.reserved, self.reserved, "reserved"))
        self.event = {
            "type": "model",
            "callId": self.id, "startedAt": datetime.now(UTC).isoformat(),
            "request": safe_payload(body), "status": "running", "reservedCny": self.reserved,
        }
        if _events.get() is not None:
            _events.get().append(self.event)
        self._save()

    def finish(self, response: dict | None = None, error: Exception | None = None):
        usage = (response or {}).get("usage") or {}
        known = isinstance(usage.get("prompt_tokens"), int) and isinstance(usage.get("completion_tokens"), int)
        charge = ((usage["prompt_tokens"] * 3 + usage["completion_tokens"] * 9) / 1_000_000) if known else self.reserved
        self.event.update({
            "status": "failed" if error else "success", "response": safe_payload(response),
            "error": type(error).__name__ if error else None,
            "elapsedMs": round((time.perf_counter() - self.started) * 1000, 2),
            "accountedCny": charge, "usageKnown": known,
        })
        if self.ledger:
            with sqlite3.connect(self.ledger, timeout=30) as conn:
                conn.execute("UPDATE calls SET charged=?,state=? WHERE id=?", (charge, "known" if known else "estimated", self.id))
        self._save()

    def _save(self):
        root = os.getenv("PM_AGENT_LLM_TRACE_DIR", "")
        if root:
            path = Path(root)
            path.mkdir(parents=True, exist_ok=True)
            (path / f"{self.id}.json").write_text(json.dumps(self.event, ensure_ascii=False, indent=2), encoding="utf-8")

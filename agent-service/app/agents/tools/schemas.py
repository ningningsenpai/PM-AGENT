"""Agent 工具执行上下文与结果。"""
from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Literal

from pydantic import BaseModel, Field


@dataclass(frozen=True, slots=True)
class ToolExecutionContext:
    """由可信接入层构造的工具身份与业务上下文。"""

    user_id: int
    trace_id: str
    conversation_id: int
    project_id: int | None
    iteration_id: int | None = None


class ToolExecutionResult(BaseModel):
    """统一表达成功、失败和待确认的工具 Observation。"""

    call_id: str
    tool_name: str
    status: Literal["success", "failed", "confirmation_required"]
    input: dict[str, Any] = Field(default_factory=dict)
    output: dict[str, Any] = Field(default_factory=dict)
    error_code: str | None = None
    error_message: str | None = None
    duration_ms: int = Field(default=0, ge=0)

    def observation_json(self) -> str:
        payload = {
            "status": self.status,
            "data": self.output if self.status == "success" else None,
            "error": (
                None
                if self.status == "success"
                else {
                    "code": self.error_code,
                    "message": self.error_message,
                }
            ),
        }
        return json.dumps(payload, ensure_ascii=False)

    def public_summary(self) -> str:
        if self.status == "success":
            return "工具执行成功"
        return self.error_message or "工具执行失败"

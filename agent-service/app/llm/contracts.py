"""LLM 原生工具调用的统一传输契约。"""

from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import BaseModel, Field, model_validator

from app.streaming.metrics import LLMTokenUsage


class LLMCapabilities(BaseModel):
    """描述模型客户端已经实现并验证的运行能力。"""

    native_tool_calling: bool = False
    streaming_tool_calling: bool = False
    parallel_tool_calling: bool = False
    reasoning_content_round_trip: bool = False


class LLMToolCall(BaseModel):
    """模型返回的单个函数调用，保留原始 JSON 参数等待执行器校验。"""

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    arguments_json: str = "{}"


class LLMAssistantTurn(BaseModel):
    """一次完整模型决策，可返回文本或一个以上工具调用。"""

    content: str = ""
    tool_calls: list[LLMToolCall] = Field(default_factory=list)
    finish_reason: str | None = None
    reasoning_content: str | None = None
    usage: LLMTokenUsage | None = None

    @model_validator(mode="after")
    def unique_call_ids(self):
        """同一次模型决策中的调用 ID 必须唯一，避免结果关联歧义。"""
        ids = [call.id for call in self.tool_calls]
        if len(ids) != len(set(ids)):
            raise ValueError("模型返回了重复的工具调用 ID")
        return self


class LLMToolCallDelta(BaseModel):
    """流式响应中的工具调用增量。"""

    index: int = Field(ge=0)
    id: str | None = None
    name: str = ""
    arguments_delta: str = ""


class LLMTurnStreamEvent(BaseModel):
    """Provider 无关的单次模型流式事件。"""

    content_delta: str = ""
    reasoning_content_delta: str = ""
    tool_call_deltas: list[LLMToolCallDelta] = Field(default_factory=list)
    finish_reason: str | None = None
    usage: LLMTokenUsage | None = None


@dataclass(slots=True)
class LLMTurnAccumulator:
    """聚合流式参数片段，形成可继续回传模型的完整 assistant 轮次。"""

    _content: list[str] = field(default_factory=list)
    _reasoning_content: list[str] = field(default_factory=list)
    _tool_calls: dict[int, dict[str, str]] = field(default_factory=dict)
    _finish_reason: str | None = None
    _usage: LLMTokenUsage | None = None

    def add(self, event: LLMTurnStreamEvent) -> None:
        if event.content_delta:
            self._content.append(event.content_delta)
        if event.reasoning_content_delta:
            self._reasoning_content.append(event.reasoning_content_delta)
        for delta in event.tool_call_deltas:
            current = self._tool_calls.setdefault(
                delta.index,
                {"id": "", "name": "", "arguments": ""},
            )
            if delta.id:
                current["id"] = delta.id
            current["name"] += delta.name
            current["arguments"] += delta.arguments_delta
        if event.finish_reason:
            self._finish_reason = event.finish_reason
        if event.usage:
            self._usage = event.usage

    def build(self) -> LLMAssistantTurn:
        calls = [
            LLMToolCall(
                id=value["id"],
                name=value["name"],
                arguments_json=value["arguments"] or "{}",
            )
            for _, value in sorted(self._tool_calls.items())
        ]
        reasoning_content = "".join(self._reasoning_content) or None
        return LLMAssistantTurn(
            content="".join(self._content),
            tool_calls=calls,
            finish_reason=self._finish_reason,
            reasoning_content=reasoning_content,
            usage=self._usage,
        )

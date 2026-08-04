"""LLM 工具调用契约测试。"""

from app.llm.contracts import (
    LLMToolCallDelta,
    LLMTurnAccumulator,
    LLMTurnStreamEvent,
)


def test_turn_accumulator_merges_streamed_tool_arguments() -> None:
    accumulator = LLMTurnAccumulator()
    accumulator.add(
        LLMTurnStreamEvent(
            tool_call_deltas=[
                LLMToolCallDelta(
                    index=0,
                    id="call-1",
                    name="get_current_project",
                    arguments_delta="{",
                )
            ]
        )
    )
    accumulator.add(
        LLMTurnStreamEvent(
            tool_call_deltas=[
                LLMToolCallDelta(index=0, arguments_delta="}"),
            ],
            finish_reason="tool_calls",
        )
    )

    turn = accumulator.build()

    assert turn.finish_reason == "tool_calls"
    assert turn.tool_calls[0].id == "call-1"
    assert turn.tool_calls[0].name == "get_current_project"
    assert turn.tool_calls[0].arguments_json == "{}"

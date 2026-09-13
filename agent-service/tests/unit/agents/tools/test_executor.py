"""Agent 工具注册和执行测试。"""
from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock

from app.agents.tools import ToolExecutionContext, ToolExecutor, ToolRegistry
from app.agents.tools.project import GetCurrentProjectTool
from app.llm.contracts import LLMToolCall
from app.modules.project.schemas import ProjectResponse


def _context() -> ToolExecutionContext:
    return ToolExecutionContext(
        user_id=1,
        trace_id="trace-1",
        conversation_id=20,
        project_id=10,
    )


def _project_response() -> ProjectResponse:
    now = datetime(2026, 8, 3, 10, 0, 0, tzinfo=UTC)
    return ProjectResponse(
        id=10,
        project_name="PM-Agent",
        status="active",
        created_at=now,
        updated_at=now,
    )


class TestToolExecutor(IsolatedAsyncioTestCase):
    async def test_validates_and_calls_project_service(self) -> None:
        projects = SimpleNamespace(get_owned=AsyncMock(return_value=_project_response()))
        registry = ToolRegistry([GetCurrentProjectTool(projects)])
        executor = ToolExecutor(registry)

        result = await executor.execute(
            LLMToolCall(
                id="call-1",
                name="get_current_project",
                arguments_json="{}",
            ),
            _context(),
        )

        self.assertEqual(result.status, "success")
        self.assertEqual(result.output["project_name"], "PM-Agent")
        projects.get_owned.assert_awaited_once_with(1, 10)

    async def test_rejects_invalid_arguments_before_service(self) -> None:
        projects = SimpleNamespace(get_owned=AsyncMock(return_value=_project_response()))
        registry = ToolRegistry([GetCurrentProjectTool(projects)])

        result = await ToolExecutor(registry).execute(
            LLMToolCall(
                id="call-1",
                name="get_current_project",
                arguments_json='{"unexpected": true}',
            ),
            _context(),
        )

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.error_code, "TOOL_ARGUMENT_INVALID")
        projects.get_owned.assert_not_awaited()

    async def test_returns_observation_for_unknown_tool(self) -> None:
        result = await ToolExecutor(ToolRegistry()).execute(
            LLMToolCall(id="call-1", name="unknown_tool", arguments_json="{}"),
            _context(),
        )

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.error_code, "TOOL_NOT_REGISTERED")

    async def test_rejects_registered_tool_outside_current_request_allowlist(self) -> None:
        projects = SimpleNamespace(get_owned=AsyncMock(return_value=_project_response()))
        registry = ToolRegistry([GetCurrentProjectTool(projects)])

        result = await ToolExecutor(registry).execute(
            LLMToolCall(
                id="call-1",
                name="get_current_project",
                arguments_json="{}",
            ),
            _context(),
            allowed_tools={"retrieve_project_context"},
        )

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.error_code, "TOOL_NOT_REGISTERED")
        self.assertIn("当前请求未开放工具", result.error_message)
        projects.get_owned.assert_not_awaited()

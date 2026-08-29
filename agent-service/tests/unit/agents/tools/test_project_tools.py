"""项目只读 Agent 工具测试。"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

from app.agents.dependencies import get_project_chat_agent
from app.agents.tools import ToolExecutionContext, ToolExecutor, ToolRegistry
from app.agents.tools.project import (
    ListCurrentProjectFilesTool,
    ListOwnedProjectsTool,
    RetrieveProjectContextTool,
)
from app.input_context import RetrievalResult
from app.llm.contracts import LLMToolCall
from app.modules.project.schemas import ProjectResponse
from app.modules.project_file.management.schemas import ProjectFileResponse


def _context(project_id: int | None = 10) -> ToolExecutionContext:
    return ToolExecutionContext(
        user_id=1,
        trace_id="trace-1",
        conversation_id=20,
        project_id=project_id,
    )


def _project_response(project_id: int = 10) -> ProjectResponse:
    now = datetime(2026, 8, 18, 10, 0, 0, tzinfo=UTC)
    return ProjectResponse(
        id=project_id,
        project_name=f"项目-{project_id}",
        status="active",
        created_at=now,
        updated_at=now,
    )


def _file_response() -> ProjectFileResponse:
    now = datetime(2026, 8, 18, 10, 0, 0, tzinfo=UTC)
    return ProjectFileResponse(
        id=30,
        project_id=10,
        business_code="project",
        relative_path="docs/README.md",
        file_name="README.md",
        storage_name="30-readme.md",
        minio_path="PM-AGENT/1/10/project/files/30-readme.md",
        extension="md",
        content_type="text/markdown",
        size_bytes=1024,
        source_mtime_ms=100,
        quick_fingerprint="quick",
        content_hash="content",
        status="active",
        upload_status="success",
        parse_attempts=1,
        lock_version=0,
        created_at=now,
        updated_at=now,
    )


class TestProjectReadTools(IsolatedAsyncioTestCase):
    def test_project_chat_agent_registers_project_read_tools(self) -> None:
        with patch(
            "app.agents.dependencies.get_settings",
            return_value=SimpleNamespace(
                llm=SimpleNamespace(),
                storage=SimpleNamespace(bucket="pm-agent"),
            ),
        ):
            agent = get_project_chat_agent(
                SimpleNamespace(),
                SimpleNamespace(),
                SimpleNamespace(),
                SimpleNamespace(),
            )

        names = [item["function"]["name"] for item in agent._registry.definitions()]
        self.assertEqual(
            [
                "get_current_project",
                "list_current_project_files",
                "list_owned_projects",
                "retrieve_project_context",
            ],
            names,
        )

    async def test_retrieve_project_context_uses_trusted_context(self) -> None:
        retriever = SimpleNamespace(
            retrieve=AsyncMock(
                return_value=RetrievalResult(
                    query="当前项目风险",
                    no_evidence=True,
                )
            )
        )
        registry = ToolRegistry([RetrieveProjectContextTool(retriever)])

        result = await ToolExecutor(registry).execute(
            LLMToolCall(
                id="call-retrieval",
                name="retrieve_project_context",
                arguments_json='{"query":"当前项目风险","limit":5}',
            ),
            _context(),
        )

        self.assertEqual("success", result.status)
        arguments = retriever.retrieve.await_args.args[1]
        self.assertEqual("当前项目风险", arguments.query)
        self.assertEqual(10, retriever.retrieve.await_args.args[0].project_id)

    async def test_retrieve_project_context_rejects_identity_override(self) -> None:
        retriever = SimpleNamespace(retrieve=AsyncMock())
        registry = ToolRegistry([RetrieveProjectContextTool(retriever)])

        result = await ToolExecutor(registry).execute(
            LLMToolCall(
                id="call-retrieval",
                name="retrieve_project_context",
                arguments_json='{"query":"风险","project_id":99}',
            ),
            _context(),
        )

        self.assertEqual("failed", result.status)
        self.assertEqual("TOOL_ARGUMENT_INVALID", result.error_code)
        retriever.retrieve.assert_not_awaited()

    async def test_list_owned_projects_uses_context_user(self) -> None:
        projects = SimpleNamespace(
            list_owned=AsyncMock(
                return_value=[_project_response(10), _project_response(11)]
            )
        )
        registry = ToolRegistry([ListOwnedProjectsTool(projects)])

        result = await ToolExecutor(registry).execute(
            LLMToolCall(
                id="call-1",
                name="list_owned_projects",
                arguments_json="{}",
            ),
            _context(),
        )

        self.assertEqual("success", result.status)
        self.assertEqual(2, result.output["total"])
        self.assertEqual([10, 11], [item["id"] for item in result.output["projects"]])
        projects.list_owned.assert_awaited_once_with(1)

    async def test_list_current_project_files_returns_safe_fields(self) -> None:
        files = SimpleNamespace(list_files=AsyncMock(return_value=[_file_response()]))
        registry = ToolRegistry([ListCurrentProjectFilesTool(files)])

        result = await ToolExecutor(registry).execute(
            LLMToolCall(
                id="call-1",
                name="list_current_project_files",
                arguments_json='{"business_code": "project"}',
            ),
            _context(),
        )

        self.assertEqual("success", result.status)
        self.assertEqual(1, result.output["total"])
        self.assertEqual("README.md", result.output["files"][0]["file_name"])
        self.assertNotIn("storage_name", result.output["files"][0])
        self.assertNotIn("minio_path", result.output["files"][0])
        files.list_files.assert_awaited_once_with(1, 10, "project")

    async def test_list_current_project_files_rejects_context_override(self) -> None:
        files = SimpleNamespace(list_files=AsyncMock())
        registry = ToolRegistry([ListCurrentProjectFilesTool(files)])

        result = await ToolExecutor(registry).execute(
            LLMToolCall(
                id="call-1",
                name="list_current_project_files",
                arguments_json='{"project_id": 99}',
            ),
            _context(),
        )

        self.assertEqual("failed", result.status)
        self.assertEqual("TOOL_ARGUMENT_INVALID", result.error_code)
        files.list_files.assert_not_awaited()

    async def test_list_current_project_files_requires_project_context(self) -> None:
        files = SimpleNamespace(list_files=AsyncMock())
        registry = ToolRegistry([ListCurrentProjectFilesTool(files)])

        result = await ToolExecutor(registry).execute(
            LLMToolCall(
                id="call-1",
                name="list_current_project_files",
                arguments_json="{}",
            ),
            _context(project_id=None),
        )

        self.assertEqual("failed", result.status)
        self.assertEqual("PARAM_INVALID", result.error_code)
        files.list_files.assert_not_awaited()

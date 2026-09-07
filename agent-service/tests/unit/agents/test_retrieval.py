"""Agent 项目上下文召回归属门禁测试。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock

from app.agents.retrieval import AgentInputContextGateway
from app.agents.tools import ToolExecutionContext
from app.core.errors import AppException, ErrorCode
from app.input_context import RetrievalQuery, RetrievalResult


def _context() -> ToolExecutionContext:
    return ToolExecutionContext(
        user_id=1,
        project_id=10,
        trace_id="trace-1",
        conversation_id=20,
    )


class TestAgentInputContextGateway(IsolatedAsyncioTestCase):
    async def test_checks_project_ownership_before_retrieval(self) -> None:
        projects = SimpleNamespace(get_owned=AsyncMock(return_value=SimpleNamespace()))
        retrieval = SimpleNamespace(
            retrieve=AsyncMock(
                return_value=RetrievalResult(query="项目风险", no_evidence=True)
            )
        )
        gateway = AgentInputContextGateway(projects, retrieval)

        result = await gateway.retrieve(
            _context(),
            RetrievalQuery(query="项目风险"),
        )

        self.assertTrue(result.no_evidence)
        projects.get_owned.assert_awaited_once_with(1, 10)
        retrieval.retrieve.assert_awaited_once()
        self.assertEqual(1, retrieval.retrieve.await_args.kwargs["user_id"])
        self.assertEqual(10, retrieval.retrieve.await_args.kwargs["project_id"])
        self.assertEqual("trace-1", retrieval.retrieve.await_args.kwargs["trace_id"])

    async def test_does_not_read_minio_when_project_is_not_owned(self) -> None:
        projects = SimpleNamespace(
            get_owned=AsyncMock(side_effect=AppException(ErrorCode.PROJECT_NOT_FOUND))
        )
        retrieval = SimpleNamespace(retrieve=AsyncMock())
        gateway = AgentInputContextGateway(projects, retrieval)

        with self.assertRaises(AppException):
            await gateway.retrieve(
                _context(),
                RetrievalQuery(query="项目风险"),
            )

        retrieval.retrieve.assert_not_awaited()

    async def test_prepare_checks_ownership_before_input_context(self) -> None:
        projects = SimpleNamespace(get_owned=AsyncMock(return_value=SimpleNamespace()))
        retrieval = SimpleNamespace()
        input_context = SimpleNamespace(
            prepare=AsyncMock(return_value=SimpleNamespace())
        )
        gateway = AgentInputContextGateway(projects, retrieval, input_context)

        await gateway.prepare(_context(), "当前项目风险")

        projects.get_owned.assert_awaited_once_with(1, 10)
        input_context.prepare.assert_awaited_once_with(
            user_id=1,
            project_id=10,
            raw_query="当前项目风险",
            trace_id="trace-1",
        )

    async def test_persistent_context_requests_source_after_ownership_check(self):
        projects = SimpleNamespace(get_owned=AsyncMock())
        contexts = SimpleNamespace(list_entries=AsyncMock(return_value=[]))
        prepared = SimpleNamespace(
            retrieval=RetrievalResult(query="文档原日期", no_evidence=True)
        )
        input_context = SimpleNamespace(prepare=AsyncMock(return_value=prepared))
        gateway = AgentInputContextGateway(
            projects, SimpleNamespace(), input_context, contexts=contexts
        )

        await gateway.prepare(_context(), "文档原日期")

        input_context.prepare.assert_awaited_once_with(
            user_id=1,
            project_id=10,
            raw_query="文档原日期",
            trace_id="trace-1",
            include_source=True,
        )
        projects.get_owned.side_effect = AppException(ErrorCode.PROJECT_NOT_FOUND)
        with self.assertRaises(AppException):
            await gateway.prepare(_context(), "文档原日期")
        self.assertEqual(1, input_context.prepare.await_count)
        self.assertEqual(1, contexts.list_entries.await_count)

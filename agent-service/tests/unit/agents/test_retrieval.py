"""Agent 项目上下文召回归属门禁测试。"""
from __future__ import annotations

from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock

from app.agents.retrieval import AgentProjectContextRetriever
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


class TestAgentProjectContextRetriever(IsolatedAsyncioTestCase):
    async def test_checks_project_ownership_before_retrieval(self) -> None:
        projects = SimpleNamespace(get_owned=AsyncMock(return_value=SimpleNamespace()))
        retrieval = SimpleNamespace(
            retrieve=AsyncMock(
                return_value=RetrievalResult(query="项目风险", no_evidence=True)
            )
        )
        retriever = AgentProjectContextRetriever(projects, retrieval)

        result = await retriever.retrieve(
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
            get_owned=AsyncMock(
                side_effect=AppException(ErrorCode.PROJECT_NOT_FOUND)
            )
        )
        retrieval = SimpleNamespace(retrieve=AsyncMock())
        retriever = AgentProjectContextRetriever(projects, retrieval)

        with self.assertRaises(AppException):
            await retriever.retrieve(
                _context(),
                RetrievalQuery(query="项目风险"),
            )

        retrieval.retrieve.assert_not_awaited()

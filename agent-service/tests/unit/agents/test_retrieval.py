"""Agent 项目上下文召回归属门禁测试。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock

from app.agents.retrieval import AgentInputContextGateway
from app.agents.tools import ToolExecutionContext
from app.core.errors import AppException, ErrorCode
from app.input_context import RetrievalHit, RetrievalQuery, RetrievalResult


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

    async def test_fixed_context_cannot_replace_gated_retrieval_hits(self) -> None:
        projects = SimpleNamespace(get_owned=AsyncMock())
        contexts = SimpleNamespace(
            list_entries=AsyncMock(
                return_value=[
                    {
                        "id": "legacy-rule",
                        "kind": "project_rule",
                        "content": "旧固定文件规则",
                        "status": "active",
                        "version": 1,
                    }
                ]
            )
        )
        gated_hit = RetrievalHit(
            source_type="source_file",
            source_id="301",
            title="app/current.py",
            summary="统一证据门禁确认的当前实现",
            score=2.5,
        )
        retrieval = SimpleNamespace(
            retrieve=AsyncMock(
                return_value=RetrievalResult(
                    query="当前规则",
                    hits=[gated_hit],
                    no_evidence=False,
                )
            )
        )
        gateway = AgentInputContextGateway(projects, retrieval, contexts=contexts)
        request = RetrievalQuery(query="当前规则", focus="specification", limit=1)

        result = await gateway.retrieve(_context(), request)

        self.assertEqual([gated_hit], result.hits)
        retrieval.retrieve.assert_awaited_once_with(
            user_id=1,
            project_id=10,
            request=request,
            trace_id="trace-1",
        )
        contexts.list_entries.assert_not_awaited()

    async def test_prepare_only_loads_active_presentation_preferences(self) -> None:
        projects = SimpleNamespace(get_owned=AsyncMock())
        contexts = SimpleNamespace(
            list_entries=AsyncMock(
                return_value=[
                    {
                        "id": "legacy-rule",
                        "kind": "project_rule",
                        "content": "旧固定文件规则",
                        "status": "active",
                        "version": 1,
                    },
                    {
                        "id": "expired-memory",
                        "kind": "long_memory",
                        "content": "已经失效的项目结论",
                        "status": "invalid",
                        "version": 3,
                    },
                    {
                        "id": "active-habit",
                        "kind": "habit",
                        "content": "请使用简洁表格",
                        "conditions": ["项目进度问答"],
                        "status": "active",
                        "version": 2,
                        "attributes": {"sourceRefs": ["不应进入表达偏好"]},
                    },
                    {
                        "id": "invalid-habit",
                        "kind": "habit",
                        "content": "已经失效的表达习惯",
                        "status": "invalid",
                        "version": 4,
                    },
                ]
            )
        )
        prepared = SimpleNamespace(
            retrieval=RetrievalResult(query="文档原日期", no_evidence=True),
            learned_entries=[],
            learned_terms=["旧固定词条"],
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
        )
        contexts.list_entries.assert_awaited_once_with(1, 10, kind="habit")
        self.assertEqual([], prepared.retrieval.hits)
        self.assertTrue(prepared.retrieval.no_evidence)
        self.assertEqual(
            [
                {
                    "id": "active-habit",
                    "kind": "habit",
                    "content": "请使用简洁表格",
                    "conditions": ["项目进度问答"],
                    "version": 2,
                }
            ],
            prepared.learned_entries,
        )
        self.assertEqual([], prepared.learned_terms)
        projects.get_owned.side_effect = AppException(ErrorCode.PROJECT_NOT_FOUND)
        with self.assertRaises(AppException):
            await gateway.prepare(_context(), "文档原日期")
        self.assertEqual(1, input_context.prepare.await_count)
        self.assertEqual(1, contexts.list_entries.await_count)

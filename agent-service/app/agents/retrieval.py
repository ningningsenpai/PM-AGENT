"""Agent 侧项目归属校验与输入上下文门面。"""

from __future__ import annotations

from app.agents.tools.schemas import ToolExecutionContext
from app.core.errors import AppException, ErrorCode
from app.input_context import (
    InputContextRetrievalService,
    RetrievalEvidence,
    RetrievalHit,
    RetrievalQuery,
    RetrievalResult,
    UserInputContext,
    UserInputContextService,
)
from app.modules.project.service import ProjectService


class AgentInputContextGateway:
    """在任何项目对象读取前通过公开 ProjectService 校验归属。"""

    def __init__(
        self,
        projects: ProjectService,
        retrieval: InputContextRetrievalService,
        input_context: UserInputContextService | None = None,
        *,
        contexts=None,
    ) -> None:
        self._projects = projects
        self._retrieval = retrieval
        self._input_context = input_context or UserInputContextService(retrieval)
        self._contexts = contexts

    async def retrieve(
        self,
        context: ToolExecutionContext,
        request: RetrievalQuery,
    ) -> RetrievalResult:
        project_id = await self._owned_project_id(context)
        entries, terms = await self._learned(context, request.query)
        expanded = (
            request.model_copy(
                update={"query": (request.query + " " + " ".join(terms))[:2000]}
            )
            if terms
            else request
        )
        result = await self._retrieval.retrieve(
            user_id=context.user_id,
            project_id=project_id,
            request=expanded,
            trace_id=context.trace_id,
        )
        return (
            self._merge(result, entries, request)
            if self._contexts is not None
            else result
        )

    async def prepare(
        self,
        context: ToolExecutionContext,
        raw_query: str,
    ) -> UserInputContext:
        project_id = await self._owned_project_id(context)
        entries, terms = await self._learned(context, raw_query)
        result = await self._input_context.prepare(
            user_id=context.user_id,
            project_id=project_id,
            raw_query=(raw_query + " " + " ".join(terms))[:2000]
            if terms
            else raw_query,
            trace_id=context.trace_id,
            **({"include_source": True} if self._contexts is not None else {}),
        )
        if self._contexts is not None:
            result.retrieval = self._merge(
                result.retrieval, entries, RetrievalQuery(query=raw_query[:2000])
            )
            result.learned_entries = entries[:50]
            result.learned_terms = terms
        return result

    async def _learned(self, context, query):
        if self._contexts is None:
            return [], []
        from app.modules.chat.context.lexicon import learned_terms

        entries = await self._contexts.list_entries(
            context.user_id, context.project_id, query=query
        )
        return entries, learned_terms(
            context.user_id, context.project_id, query, entries
        )

    async def release_reads(self):
        if self._contexts is not None:
            await self._contexts.release_reads()

    @staticmethod
    def _merge(result, entries, request):
        types = {
            "habit": "user_habit",
            "short_memory": "short_term_memory",
            "long_memory": "long_term_memory",
        }
        # 已迁移内容以 MySQL 为准，旧 MinIO 记忆不能绕过失效和版本过滤。
        hits = [
            hit for hit in result.hits if hit.source_type not in set(types.values())
        ]
        learned = []
        for entry in entries:
            kind = entry["kind"]
            if kind not in types or request.focus in (
                "files",
                "specification",
                "changes",
            ):
                continue
            if (
                request.focus == "memory"
                and kind == "habit"
                or request.focus == "habits"
                and kind != "habit"
            ):
                continue
            learned.append(
                RetrievalHit(
                    source_type=types[kind],
                    source_id=f"entry:{entry['id']}:v{entry['version']}",
                    title=entry["attributes"].get("key", kind),
                    summary=entry["content"],
                    score=1,
                    evidence=[
                        RetrievalEvidence(
                            text=entry["content"],
                            kind="user_statement",
                            logical_path=f"conversation/message/{entry['sourceMessageId']}",
                        )
                    ],
                )
            )
        result.hits = (learned + hits)[: request.limit]
        result.no_evidence = not result.hits
        return result

    async def _owned_project_id(self, context: ToolExecutionContext) -> int:
        if context.project_id is None:
            raise AppException(ErrorCode.PARAM_INVALID, "当前对话未指定项目")
        await self._projects.get_owned(context.user_id, context.project_id)
        return context.project_id


# 兼容现有测试和内部导入，新增代码统一使用 AgentInputContextGateway。
AgentProjectContextRetriever = AgentInputContextGateway

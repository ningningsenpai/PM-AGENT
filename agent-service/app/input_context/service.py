"""用户输入归一化与前置召回的统一用例。"""

from __future__ import annotations

from app.input_context.retrieval import InputContextRetrievalService, RetrievalQuery
from app.input_context.retrieval.policy import (
    DEFAULT_RETRIEVAL_POLICY,
    RetrievalPolicy,
)
from app.input_context.schemas import UserInputContext


class UserInputContextService:
    """在可信身份已确认后组装当前轮用户输入上下文。"""

    def __init__(
        self,
        retrieval: InputContextRetrievalService,
        policy: RetrievalPolicy = DEFAULT_RETRIEVAL_POLICY,
    ) -> None:
        self._retrieval = retrieval
        self._policy = policy

    async def prepare(
        self,
        *,
        user_id: int,
        project_id: int,
        raw_query: str,
        trace_id: str | None = None,
        include_source: bool = False,
    ) -> UserInputContext:
        """归一化当前问题，按调用方要求在既有配额内补充原文。"""
        normalization = self._retrieval.normalize_query(
            raw_query,
            project_id=project_id,
        )
        retrieval = await self._retrieval.retrieve(
            user_id=user_id,
            project_id=project_id,
            request=RetrievalQuery(
                query=raw_query[: self._policy.max_query_chars],
                evidence_level="source" if include_source else "summary",
                limit=self._policy.pre_retrieval_limit,
            ),
            trace_id=trace_id,
            normalization=normalization,
        )
        warnings = list(dict.fromkeys([*normalization.warnings, *retrieval.warnings]))
        return UserInputContext(
            raw_query=raw_query,
            normalization=normalization.result,
            retrieval=retrieval,
            warnings=warnings,
            degraded=normalization.degraded or retrieval.degraded,
        )

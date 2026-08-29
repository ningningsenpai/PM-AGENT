"""在线输入上下文召回用例编排。"""

from __future__ import annotations

from time import perf_counter

from app.core.errors import AppException, ErrorCode
from app.core.logger import get_logger
from app.infrastructure.storage import ObjectStorage, StorageLocationFactory
from app.input_context.normalization import NormalizationService
from app.input_context.normalization.query import QueryNormalization, QueryNormalizer
from app.input_context.retrieval.candidate import RetrievalCandidate
from app.input_context.retrieval.evidence import RawEvidenceLoader
from app.input_context.retrieval.planning import RetrievalPlanner
from app.input_context.retrieval.policy import (
    DEFAULT_RETRIEVAL_POLICY,
    RetrievalPolicy,
)
from app.input_context.retrieval.ranking import RetrievalRanker
from app.input_context.retrieval.schemas import (
    RetrievalHit,
    RetrievalQuery,
    RetrievalResult,
)
from app.input_context.retrieval.snapshot import ProjectSnapshotReader
from app.input_context.retrieval.sources import RetrievalCandidateSource
from app.project_context.file_detail.extraction import FileContentExtractionService

logger = get_logger(__name__)


class InputContextRetrievalService:
    """协调归一化、计划生成、可信读取、排序和证据补充。"""

    def __init__(
        self,
        storage: ObjectStorage,
        locations: StorageLocationFactory,
        normalization: NormalizationService,
        extraction: FileContentExtractionService,
        policy: RetrievalPolicy = DEFAULT_RETRIEVAL_POLICY,
    ) -> None:
        reader = ProjectSnapshotReader(storage, locations)
        ranker = RetrievalRanker()
        self._query_normalizer = QueryNormalizer(normalization)
        self._planner = RetrievalPlanner(policy)
        self._candidate_source = RetrievalCandidateSource(reader, ranker)
        self._raw_evidence = RawEvidenceLoader(reader, extraction, policy)
        self._reader = reader
        self._ranker = ranker
        self._policy = policy
        self._result_cache: dict[
            tuple[int, int, str, str, str, int], RetrievalResult
        ] = {}
        self._unique_retrievals = 0

    def normalize_query(self, raw_query: str, *, project_id: int) -> QueryNormalization:
        """复用同一归一化依赖生成可显式降级的查询结果。"""
        return self._query_normalizer.normalize(raw_query, project_id=project_id)

    async def retrieve(
        self,
        *,
        user_id: int,
        project_id: int,
        request: RetrievalQuery,
        trace_id: str | None = None,
        normalization: QueryNormalization | None = None,
    ) -> RetrievalResult:
        """在可信项目身份下执行一次可缓存召回。"""
        cache_key = (
            user_id,
            project_id,
            request.query,
            request.focus,
            request.evidence_level,
            request.limit,
        )
        cached = self._result_cache.get(cache_key)
        if cached is not None:
            return cached.model_copy(deep=True)
        if self._unique_retrievals >= self._policy.max_unique_retrievals:
            raise AppException(
                ErrorCode.AGENT_TOOL_LOOP_LIMIT_EXCEEDED,
                "单次 Agent 请求最多执行三次项目上下文召回",
            )
        self._unique_retrievals += 1

        started_at = perf_counter()
        normalized = normalization or self.normalize_query(
            request.query,
            project_id=project_id,
        )
        warnings = list(normalized.warnings)
        plan = self._planner.build(request, normalized)
        snapshot = await self._reader.load(user_id, project_id, warnings)
        if snapshot is None:
            result = RetrievalResult(
                query=request.query,
                normalized_terms=list(plan.normalized_terms),
                warnings=self._unique(warnings),
                degraded=True,
                no_evidence=True,
            )
            self._result_cache[cache_key] = result
            return result.model_copy(deep=True)

        candidates = await self._candidate_source.build(snapshot, plan, warnings)
        ranked = self._ranker.score_all(candidates, plan)
        await self._candidate_source.hydrate_details(
            ranked,
            snapshot,
            plan,
            warnings,
        )
        ranked = self._ranker.sort(ranked)
        selected = ranked[: plan.result_limit]

        if plan.read_source:
            await self._raw_evidence.hydrate(selected, snapshot, warnings)

        result = RetrievalResult(
            query=request.query,
            normalized_terms=list(plan.normalized_terms),
            index_updated_at=snapshot.index.updated_at,
            hits=[self._to_hit(candidate) for candidate in selected],
            warnings=self._unique(warnings),
            degraded=normalized.degraded or bool(warnings),
            no_evidence=not selected,
        )
        self._result_cache[cache_key] = result
        logger.info(
            "项目上下文召回完成 action=input.context.retrieve traceId=%s "
            "projectId=%s hits=%s degraded=%s costMs=%s",
            trace_id or "-",
            project_id,
            len(result.hits),
            result.degraded,
            round((perf_counter() - started_at) * 1000),
        )
        return result.model_copy(deep=True)

    @staticmethod
    def _to_hit(candidate: RetrievalCandidate) -> RetrievalHit:
        return RetrievalHit(
            source_type=candidate.source_type,
            source_id=candidate.source_id,
            title=candidate.title,
            summary=candidate.summary,
            score=round(candidate.score, 4),
            logical_path=candidate.logical_path,
            file_id=candidate.file_id,
            content_hash=candidate.content_hash,
            detail_ref=candidate.detail_ref,
            importance=candidate.importance,
            evidence=candidate.evidence[:10],
        )

    @staticmethod
    def _unique(values: list[str]) -> list[str]:
        return list(dict.fromkeys(values))

"""多来源候选生成和文件详情补充的协调器。"""

from __future__ import annotations

from app.input_context.retrieval.candidate import RetrievalCandidate
from app.input_context.retrieval.planning import RetrievalPlan
from app.input_context.retrieval.ranking import RetrievalRanker
from app.input_context.retrieval.snapshot import ProjectSnapshot, ProjectSnapshotReader
from app.input_context.retrieval.sources.base import (
    CandidateProvider,
    RecordCandidateFactory,
)
from app.input_context.retrieval.sources.details import FileDetailHydrator
from app.input_context.retrieval.sources.files import FileCandidateProvider
from app.input_context.retrieval.sources.system import (
    HabitCandidateProvider,
    MemoryCandidateProvider,
    SpecificationCandidateProvider,
    UpdateJournalCandidateProvider,
)


class RetrievalCandidateSource:
    """按召回计划协调独立 Provider，不参与最终排序。"""

    def __init__(
        self,
        reader: ProjectSnapshotReader,
        ranker: RetrievalRanker,
    ) -> None:
        factory = RecordCandidateFactory()
        self._providers: tuple[CandidateProvider, ...] = (
            FileCandidateProvider(),
            SpecificationCandidateProvider(reader, factory),
            MemoryCandidateProvider(reader, factory),
            HabitCandidateProvider(reader, factory),
            UpdateJournalCandidateProvider(reader, factory),
        )
        self._details = FileDetailHydrator(reader, ranker)

    async def build(
        self,
        snapshot: ProjectSnapshot,
        plan: RetrievalPlan,
        warnings: list[str],
    ) -> list[RetrievalCandidate]:
        candidates: list[RetrievalCandidate] = []
        for provider in self._providers:
            if not provider.source_types.intersection(plan.allowed_source_types):
                continue
            candidates.extend(await provider.collect(snapshot, plan, warnings))
        return candidates

    async def hydrate_details(
        self,
        ranked: list[RetrievalCandidate],
        snapshot: ProjectSnapshot,
        plan: RetrievalPlan,
        warnings: list[str],
    ) -> None:
        await self._details.hydrate(ranked, snapshot, plan, warnings)

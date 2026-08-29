"""项目文件索引候选来源。"""

from __future__ import annotations

from app.input_context.retrieval.candidate import RetrievalCandidate
from app.input_context.retrieval.planning import RetrievalPlan
from app.input_context.retrieval.schemas import RetrievalEvidence
from app.input_context.retrieval.snapshot import ProjectSnapshot


class FileCandidateProvider:
    """只从可信索引中的有效项目文件生成候选。"""

    source_types = frozenset({"file_detail"})

    async def collect(
        self,
        snapshot: ProjectSnapshot,
        _plan: RetrievalPlan,
        _warnings: list[str],
    ) -> list[RetrievalCandidate]:
        candidates: list[RetrievalCandidate] = []
        for entry in [*snapshot.index.project, *snapshot.index.user]:
            if entry.status != "active" or not entry.detail_ref:
                continue
            candidates.append(
                RetrievalCandidate(
                    source_type="file_detail",
                    source_id=f"file-{entry.id}",
                    title=entry.file_name,
                    summary=entry.summary or "项目文件",
                    high_fields=[entry.logical_path, entry.file_name, *entry.keywords],
                    medium_fields=[entry.summary or "", *entry.keywords],
                    low_fields=[
                        entry.module or "",
                        entry.kind or "",
                        entry.file_type or "",
                        entry.language or "",
                    ],
                    logical_path=entry.logical_path,
                    file_id=entry.id,
                    content_hash=entry.content_hash,
                    detail_ref=entry.detail_ref,
                    importance=entry.importance,
                    evidence=[
                        RetrievalEvidence(
                            text=entry.summary or f"项目文件 {entry.logical_path}",
                            logical_path=entry.logical_path,
                        )
                    ],
                    file_entry=entry,
                )
            )
        return candidates

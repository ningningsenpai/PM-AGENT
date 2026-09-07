"""文件详情校验、候选补充与二次评分。"""

from __future__ import annotations

import json

from pydantic import ValidationError

from app.core.errors import AppException
from app.input_context.retrieval.candidate import RetrievalCandidate
from app.input_context.retrieval.planning import RetrievalPlan
from app.input_context.retrieval.ranking import RetrievalRanker
from app.input_context.retrieval.schemas import RetrievalEvidence
from app.input_context.retrieval.snapshot import (
    ProjectSnapshot,
    ProjectSnapshotReader,
    normalize_content_hash,
)
from app.project_context.file_detail.schemas import FileDetail


class FileDetailHydrator:
    """只为初排短名单加载经过身份和哈希校验的文件详情。"""

    def __init__(
        self,
        reader: ProjectSnapshotReader,
        ranker: RetrievalRanker,
    ) -> None:
        self._reader = reader
        self._ranker = ranker

    async def hydrate(
        self,
        ranked: list[RetrievalCandidate],
        snapshot: ProjectSnapshot,
        plan: RetrievalPlan,
        warnings: list[str],
    ) -> None:
        file_candidates = [item for item in ranked if item.file_entry is not None][
            : plan.candidate_limit
        ]
        for candidate in file_candidates:
            assert candidate.detail_ref is not None
            try:
                detail = FileDetail.model_validate(
                    await self._reader.read_json(
                        self._reader.system_location(snapshot, candidate.detail_ref)
                    )
                )
            except (AppException, json.JSONDecodeError, ValidationError, ValueError):
                warnings.append(f"文件详情不可用：{candidate.logical_path}")
                continue
            if (
                detail.project_id != snapshot.index.project_id
                or detail.file_id != candidate.file_id
                or not normalize_content_hash(detail.content_hash)
                or normalize_content_hash(detail.content_hash)
                != normalize_content_hash(candidate.content_hash)
                or detail.original_path != candidate.logical_path
                or detail.detail_ref != candidate.detail_ref
            ):
                warnings.append(
                    f"文件详情身份或内容哈希不一致：{candidate.logical_path}"
                )
                continue
            candidate.detail = detail
            candidate.source_range = self._ranker.best_source_range(detail, plan)
            candidate.high_fields.extend(
                self._join_fields(
                    detail.keywords,
                    detail.related_topics,
                    [item.get("entities") for item in detail.content_slices],
                    [
                        item.get("code")
                        for item in detail.risk_flags
                        if isinstance(item, dict)
                    ],
                )
            )
            candidate.medium_fields.extend(
                self._join_fields(
                    detail.summary,
                    detail.role,
                    detail.content_slices,
                    detail.related_files,
                    detail.risk_flags,
                    detail.evidence,
                )
            )
            candidate.score = self._ranker.score(candidate, plan)
            candidate.evidence = self._detail_evidence(detail)

    @staticmethod
    def _detail_evidence(detail: FileDetail) -> list[RetrievalEvidence]:
        evidence: list[RetrievalEvidence] = []
        for item in detail.content_slices[:3]:
            if not isinstance(item, dict):
                continue
            summary = item.get("summary")
            if not isinstance(summary, str) or not summary.strip():
                continue
            source_range = item.get("source_range")
            start_line = None
            end_line = None
            if isinstance(source_range, dict):
                start_line = source_range.get("start_line")
                end_line = source_range.get("end_line")
            evidence.append(
                RetrievalEvidence(
                    text=summary,
                    logical_path=detail.original_path,
                    start_line=start_line if isinstance(start_line, int) else None,
                    end_line=end_line if isinstance(end_line, int) else None,
                )
            )
        if not evidence:
            evidence.append(
                RetrievalEvidence(
                    text=detail.summary,
                    logical_path=detail.original_path,
                )
            )
        return evidence

    @classmethod
    def _join_fields(cls, *values: object) -> list[str]:
        result: list[str] = []
        for value in values:
            result.extend(RetrievalRanker.strings(value))
        return result

"""项目快照候选生成与文件详情补证。"""
from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from app.core.errors import AppException
from app.input_context.retrieval.candidate import RetrievalCandidate
from app.input_context.retrieval.query import QueryAnalysis
from app.input_context.retrieval.ranking import RetrievalRanker
from app.input_context.retrieval.schemas import RetrievalEvidence, RetrievalQuery
from app.input_context.retrieval.snapshot import ProjectSnapshot, ProjectSnapshotReader
from app.project_context.file_detail.schemas import FileDetail

_HABIT_FILES = ("work", "thinking", "specification", "tooling", "life")
_MAX_DETAIL_CANDIDATES = 8


class RetrievalCandidateSource:
    """将 index 和 system 文档转换为统一候选，不负责最终排序。"""

    def __init__(
        self,
        reader: ProjectSnapshotReader,
        ranker: RetrievalRanker,
    ) -> None:
        self._reader = reader
        self._ranker = ranker

    async def build(
        self,
        snapshot: ProjectSnapshot,
        request: RetrievalQuery,
        analysis: QueryAnalysis,
        warnings: list[str],
    ) -> list[RetrievalCandidate]:
        candidates = (
            self._file_candidates(snapshot)
            if request.focus in {"auto", "files"}
            else []
        )
        candidates.extend(
            await self._system_candidates(
                snapshot,
                request,
                analysis,
                warnings,
            )
        )
        return candidates

    async def hydrate_details(
        self,
        ranked: list[RetrievalCandidate],
        snapshot: ProjectSnapshot,
        analysis: QueryAnalysis,
        warnings: list[str],
    ) -> None:
        file_candidates = [
            item for item in ranked if item.file_entry is not None
        ][:_MAX_DETAIL_CANDIDATES]
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
                or detail.content_hash != candidate.content_hash
                or detail.detail_ref != candidate.detail_ref
            ):
                warnings.append(f"文件详情身份或内容哈希不一致：{candidate.logical_path}")
                continue
            candidate.detail = detail
            candidate.source_range = self._ranker.best_source_range(
                detail,
                analysis.raw_query,
                analysis.normalized_terms,
            )
            candidate.high_fields.extend(
                self._join_field_lists(
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
                self._join_field_lists(
                    detail.summary,
                    detail.role,
                    detail.content_slices,
                    detail.related_files,
                    detail.risk_flags,
                    detail.evidence,
                )
            )
            candidate.score = self._ranker.score(
                candidate,
                analysis.raw_query,
                analysis.normalized_terms,
            ) + 1.0
            candidate.evidence = self._detail_evidence(detail)

    @staticmethod
    def _file_candidates(snapshot: ProjectSnapshot) -> list[RetrievalCandidate]:
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

    async def _system_candidates(
        self,
        snapshot: ProjectSnapshot,
        request: RetrievalQuery,
        analysis: QueryAnalysis,
        warnings: list[str],
    ) -> list[RetrievalCandidate]:
        candidates: list[RetrievalCandidate] = []
        index = snapshot.index
        if request.focus in {"auto", "specification"}:
            data = await self._reader.optional_json(
                snapshot,
                index.system.project_specification,
                "项目规范",
                warnings,
            )
            if isinstance(data, dict):
                candidates.extend(self._specification_candidates(data))

        if request.focus in {"auto", "memory"}:
            for ref, key, source_type, label in (
                (
                    index.system.long_term_memory,
                    "long_term_memory",
                    "long_term_memory",
                    "长期记忆",
                ),
                (
                    index.system.short_term_memory,
                    "short_term_memory",
                    "short_term_memory",
                    "短期记忆",
                ),
            ):
                data = await self._reader.optional_json(
                    snapshot,
                    ref,
                    label,
                    warnings,
                )
                if isinstance(data, dict):
                    candidates.extend(
                        self._record_candidates(data.get(key, []), source_type)
                    )

        if analysis.include_habits:
            habits_prefix = index.system.user_habits.rstrip("/")
            for category in _HABIT_FILES:
                data = await self._reader.optional_json(
                    snapshot,
                    f"{habits_prefix}/{category}.json",
                    f"用户习惯 {category}",
                    warnings,
                )
                if isinstance(data, dict):
                    candidates.extend(
                        self._record_candidates(
                            data.get("user_habits", []),
                            "user_habit",
                        )
                    )

        if analysis.include_changes:
            candidates.extend(
                await self._journal_candidates(
                    snapshot,
                    index.system.update_journal,
                    warnings,
                )
            )
        return candidates

    def _specification_candidates(
        self,
        data: dict[str, Any],
    ) -> list[RetrievalCandidate]:
        root = data.get("project_specification", data)
        if not isinstance(root, dict):
            return []
        candidates: list[RetrievalCandidate] = []
        stage = root.get("development_stage")
        if isinstance(stage, dict):
            summary = self._join_text(
                stage.get("current_stage"),
                stage.get("stage_goal"),
                stage.get("completed"),
                stage.get("next_focus"),
            )
            candidates.append(
                RetrievalCandidate(
                    source_type="project_specification",
                    source_id="development-stage",
                    title="项目开发阶段",
                    summary=summary,
                    high_fields=self._strings(stage.get("current_stage")),
                    medium_fields=self._strings(stage),
                    evidence=[RetrievalEvidence(text=summary)],
                    importance="high",
                )
            )
        for value in root.values():
            if isinstance(value, list):
                candidates.extend(
                    self._record_candidates(value, "project_specification")
                )
        return candidates

    def _record_candidates(
        self,
        records: Any,
        source_type: str,
    ) -> list[RetrievalCandidate]:
        if not isinstance(records, list):
            return []
        candidates: list[RetrievalCandidate] = []
        for index, item in enumerate(records):
            if not isinstance(item, dict):
                continue
            summary = self._first_text(
                item,
                "rule",
                "constraint",
                "memory",
                "habit",
                "summary",
                "text",
            )
            if not summary:
                continue
            source_id = str(
                item.get("id")
                or item.get("event_id")
                or item.get("change_id")
                or f"{source_type}-{index + 1}"
            )
            title = str(item.get("title") or source_id)
            logical_path = self._first_source_path(item)
            candidates.append(
                RetrievalCandidate(
                    source_type=source_type,
                    source_id=source_id,
                    title=title,
                    summary=summary,
                    high_fields=self._join_field_lists(
                        item.get("id"),
                        item.get("tags"),
                        item.get("keywords"),
                        item.get("signals"),
                    ),
                    medium_fields=self._join_field_lists(
                        title,
                        summary,
                        item.get("related_specs"),
                        item.get("source_refs"),
                        item.get("evidence"),
                    ),
                    low_fields=self._join_field_lists(
                        item.get("scope"),
                        item.get("category"),
                        item.get("status"),
                    ),
                    logical_path=logical_path,
                    importance=self._optional_string(item.get("importance")),
                    evidence=[
                        RetrievalEvidence(text=summary, logical_path=logical_path)
                    ],
                )
            )
        return candidates

    async def _journal_candidates(
        self,
        snapshot: ProjectSnapshot,
        relative_path: str,
        warnings: list[str],
    ) -> list[RetrievalCandidate]:
        try:
            content = (
                await self._reader.read_bytes(
                    self._reader.system_location(snapshot, relative_path)
                )
            ).decode("utf-8")
            records = [
                json.loads(line) for line in content.splitlines() if line.strip()
            ]
        except (AppException, UnicodeDecodeError, json.JSONDecodeError, ValueError):
            warnings.append("更新日志无法读取或结构不合法")
            return []
        return self._record_candidates(records, "update_journal")

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
                RetrievalEvidence(text=detail.summary, logical_path=detail.original_path)
            )
        return evidence

    @staticmethod
    def _first_text(item: dict[str, Any], *keys: str) -> str:
        for key in keys:
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    @staticmethod
    def _first_source_path(item: dict[str, Any]) -> str | None:
        refs = item.get("source_refs")
        if isinstance(refs, list):
            for ref in refs:
                if isinstance(ref, dict) and isinstance(ref.get("path"), str):
                    return ref["path"]
        return None

    @classmethod
    def _join_field_lists(cls, *values: Any) -> list[str]:
        result: list[str] = []
        for value in values:
            result.extend(cls._strings(value))
        return result

    @staticmethod
    def _strings(value: Any) -> list[str]:
        return RetrievalRanker.strings(value)

    @classmethod
    def _join_text(cls, *values: Any) -> str:
        return "；".join(cls._strings(list(values)))

    @staticmethod
    def _optional_string(value: Any) -> str | None:
        return value if isinstance(value, str) else None

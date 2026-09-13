"""项目规范、记忆、习惯和更新日志候选来源。"""

from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from app.core.errors import AppException
from app.input_context.retrieval.candidate import RetrievalCandidate
from app.input_context.retrieval.planning import RetrievalPlan
from app.input_context.retrieval.snapshot import ProjectSnapshot, ProjectSnapshotReader
from app.input_context.retrieval.sources.base import RecordCandidateFactory
from app.project_context.specification.schemas import (
    RULE_SECTION_FILES,
    ProjectSpecificationManifest,
    ProjectSpecificationSectionDocument,
    effective_section_rules,
)

_HABIT_FILES = ("work", "thinking", "specification", "tooling", "life")


class SpecificationCandidateProvider:
    """从五个项目规范分区生成规则候选。"""

    source_types = frozenset({"project_specification"})

    def __init__(
        self,
        reader: ProjectSnapshotReader,
        factory: RecordCandidateFactory,
    ) -> None:
        self._reader = reader
        self._factory = factory

    async def collect(
        self,
        snapshot: ProjectSnapshot,
        _plan: RetrievalPlan,
        warnings: list[str],
    ) -> list[RetrievalCandidate]:
        data = await self._reader.optional_json(
            snapshot,
            snapshot.index.system.project_specification,
            "项目规范",
            warnings,
        )
        try:
            manifest = ProjectSpecificationManifest.model_validate(data)
        except ValidationError:
            warnings.append("项目规范清单结构不合法")
            return []
        candidates: list[RetrievalCandidate] = []
        for section_name in RULE_SECTION_FILES:
            reference = getattr(manifest.sections, section_name)
            section_data = await self._reader.optional_json(
                snapshot,
                reference.path,
                f"项目规范分区 {section_name}",
                warnings,
            )
            try:
                section = ProjectSpecificationSectionDocument.model_validate(
                    section_data
                )
            except ValidationError:
                warnings.append(f"项目规范分区结构不合法：{section_name}")
                continue
            if (
                section.project_id != snapshot.index.project_id
                or section.section != section_name
            ):
                warnings.append(f"项目规范分区身份不一致：{section_name}")
                continue
            candidates.extend(
                self._factory.from_records(
                    [
                        rule.model_dump(mode="json")
                        for rule in effective_section_rules(section)
                    ],
                    "project_specification",
                )
            )
        return candidates


class MemoryCandidateProvider:
    """按计划读取长期和短期记忆候选。"""

    source_types = frozenset({"long_term_memory", "short_term_memory"})

    def __init__(
        self,
        reader: ProjectSnapshotReader,
        factory: RecordCandidateFactory,
    ) -> None:
        self._reader = reader
        self._factory = factory

    async def collect(
        self,
        snapshot: ProjectSnapshot,
        plan: RetrievalPlan,
        warnings: list[str],
    ) -> list[RetrievalCandidate]:
        candidates: list[RetrievalCandidate] = []
        for ref, key, source_type, label in (
            (
                snapshot.index.system.long_term_memory,
                "long_term_memory",
                "long_term_memory",
                "长期记忆",
            ),
            (
                snapshot.index.system.short_term_memory,
                "short_term_memory",
                "short_term_memory",
                "短期记忆",
            ),
        ):
            if source_type not in plan.allowed_source_types:
                continue
            data = await self._reader.optional_json(snapshot, ref, label, warnings)
            if isinstance(data, dict):
                candidates.extend(
                    self._factory.from_records(data.get(key, []), source_type)
                )
        return candidates


class HabitCandidateProvider:
    """仅在计划允许时读取五类用户习惯。"""

    source_types = frozenset({"user_habit"})

    def __init__(
        self,
        reader: ProjectSnapshotReader,
        factory: RecordCandidateFactory,
    ) -> None:
        self._reader = reader
        self._factory = factory

    async def collect(
        self,
        snapshot: ProjectSnapshot,
        _plan: RetrievalPlan,
        warnings: list[str],
    ) -> list[RetrievalCandidate]:
        candidates: list[RetrievalCandidate] = []
        habits_prefix = snapshot.index.system.user_habits.rstrip("/")
        for category in _HABIT_FILES:
            data = await self._reader.optional_json(
                snapshot,
                f"{habits_prefix}/{category}.json",
                f"用户习惯 {category}",
                warnings,
            )
            if isinstance(data, dict):
                candidates.extend(
                    self._factory.from_records(
                        data.get("user_habits", []),
                        "user_habit",
                    )
                )
        return candidates


class UpdateJournalCandidateProvider:
    """从受控 JSONL 更新日志生成变更候选。"""

    source_types = frozenset({"update_journal"})

    def __init__(
        self,
        reader: ProjectSnapshotReader,
        factory: RecordCandidateFactory,
    ) -> None:
        self._reader = reader
        self._factory = factory

    async def collect(
        self,
        snapshot: ProjectSnapshot,
        _plan: RetrievalPlan,
        warnings: list[str],
    ) -> list[RetrievalCandidate]:
        try:
            content = (
                await self._reader.read_bytes(
                    self._reader.system_location(
                        snapshot,
                        snapshot.index.system.update_journal,
                    )
                )
            ).decode("utf-8")
            records: list[Any] = [
                json.loads(line) for line in content.splitlines() if line.strip()
            ]
        except (AppException, UnicodeDecodeError, json.JSONDecodeError, ValueError):
            warnings.append("更新日志无法读取或结构不合法")
            return []
        return self._factory.from_records(records, "update_journal")

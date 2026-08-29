"""召回候选来源协议与通用记录转换。"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Protocol

from app.input_context.retrieval.candidate import RetrievalCandidate
from app.input_context.retrieval.planning import RetrievalPlan
from app.input_context.retrieval.schemas import RetrievalEvidence, RetrievalSourceType
from app.input_context.retrieval.snapshot import ProjectSnapshot


class CandidateProvider(Protocol):
    """限定候选来源只负责读取一种上下文并生成统一候选。"""

    source_types: frozenset[RetrievalSourceType]

    async def collect(
        self,
        snapshot: ProjectSnapshot,
        plan: RetrievalPlan,
        warnings: list[str],
    ) -> list[RetrievalCandidate]: ...


class RecordCandidateFactory:
    """把规范、记忆、习惯和日志中的记录转换为统一候选。"""

    def from_records(
        self,
        records: Any,
        source_type: RetrievalSourceType,
    ) -> list[RetrievalCandidate]:
        if not isinstance(records, list):
            return []
        candidates: list[RetrievalCandidate] = []
        for index, item in enumerate(records):
            if not isinstance(item, dict):
                continue
            summary = self.first_text(
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
            logical_path = self.first_source_path(item)
            candidates.append(
                RetrievalCandidate(
                    source_type=source_type,
                    source_id=source_id,
                    title=title,
                    summary=summary,
                    high_fields=self.join_fields(
                        item.get("id"),
                        item.get("tags"),
                        item.get("keywords"),
                        item.get("signals"),
                    ),
                    medium_fields=self.join_fields(
                        title,
                        summary,
                        item.get("related_specs"),
                        item.get("source_refs"),
                        item.get("evidence"),
                    ),
                    low_fields=self.join_fields(
                        item.get("scope"),
                        item.get("category"),
                        item.get("status"),
                    ),
                    logical_path=logical_path,
                    importance=self.optional_string(item.get("importance")),
                    evidence=[
                        RetrievalEvidence(text=summary, logical_path=logical_path)
                    ],
                )
            )
        return candidates

    @staticmethod
    def first_text(item: dict[str, Any], *keys: str) -> str:
        for key in keys:
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    @staticmethod
    def first_source_path(item: dict[str, Any]) -> str | None:
        refs = item.get("source_refs")
        if isinstance(refs, list):
            for ref in refs:
                if isinstance(ref, dict) and isinstance(ref.get("path"), str):
                    return ref["path"]
        return None

    @classmethod
    def join_fields(cls, *values: Any) -> list[str]:
        return cls.strings(values)

    @classmethod
    def join_text(cls, *values: Any) -> str:
        return "；".join(cls.strings(values))

    @classmethod
    def strings(cls, value: Any) -> list[str]:
        if isinstance(value, str):
            return [value]
        if isinstance(value, dict):
            return cls.strings(value.values())
        if isinstance(value, Iterable):
            result: list[str] = []
            for nested in value:
                result.extend(cls.strings(nested))
            return result
        return []

    @staticmethod
    def optional_string(value: Any) -> str | None:
        return value if isinstance(value, str) else None

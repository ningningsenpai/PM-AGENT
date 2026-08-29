"""把归一化用户问题转换为确定、可解释的召回计划。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from app.input_context.normalization.query import QueryNormalization
from app.input_context.retrieval.policy import RetrievalPolicy
from app.input_context.retrieval.schemas import (
    RetrievalQuery,
    RetrievalSourceType,
)

TermSource = Literal["canonical", "technical", "raw_phrase", "chinese_fallback"]

_ASCII_TERM_PATTERN = re.compile(r"r-\d+|[a-z0-9_.$#:/-]{2,}", re.IGNORECASE)
_CHINESE_SEQUENCE_PATTERN = re.compile(r"[\u3400-\u9fff]{2,}")
_SOURCE_EVIDENCE_HINTS = (
    "代码",
    "方法",
    "类",
    "sql",
    "配置",
    "接口参数",
    "实现",
    "原文",
    "证据",
    "哪一行",
    "源码",
)
_HABIT_HINTS = ("习惯", "偏好", "喜欢", "倾向", "表达方式", "协作方式")
_CHANGE_HINTS = ("变更", "更新", "历史", "日志", "最近修改")
_CHINESE_STOP_TERMS = {
    "一下",
    "什么",
    "哪些",
    "如何",
    "怎么",
    "是否",
    "当前",
    "这个",
    "项目",
    "可以",
    "需要",
}
_TERM_WEIGHTS: dict[TermSource, float] = {
    "canonical": 1.5,
    "technical": 1.25,
    "raw_phrase": 1.0,
    "chinese_fallback": 0.5,
}


@dataclass(frozen=True, slots=True)
class WeightedTerm:
    """携带来源与权重的召回词项。"""

    text: str
    source: TermSource
    weight: float


@dataclass(frozen=True, slots=True)
class RetrievalPlan:
    """一次召回执行所需的全部确定性决策。"""

    raw_query: str
    cleaned_query: str
    terms: tuple[WeightedTerm, ...]
    allowed_source_types: frozenset[RetrievalSourceType]
    evidence_level: Literal["summary", "source"]
    candidate_limit: int
    result_limit: int

    @property
    def normalized_terms(self) -> tuple[str, ...]:
        return tuple(term.text for term in self.terms)

    @property
    def read_source(self) -> bool:
        return self.evidence_level == "source"


class RetrievalPlanner:
    """根据公共请求协议和归一化结果生成召回计划。"""

    def __init__(self, policy: RetrievalPolicy) -> None:
        self._policy = policy

    def build(
        self,
        request: RetrievalQuery,
        normalization: QueryNormalization,
    ) -> RetrievalPlan:
        terms = self._weighted_terms(normalization)
        allowed_sources = self._allowed_sources(request, normalization.raw_text)
        read_source = request.evidence_level == "source" or (
            request.evidence_level == "auto"
            and self._contains_hint(normalization.raw_text, _SOURCE_EVIDENCE_HINTS)
        )
        return RetrievalPlan(
            raw_query=normalization.raw_text,
            cleaned_query=normalization.cleaned_text,
            terms=terms,
            allowed_source_types=allowed_sources,
            evidence_level="source" if read_source else "summary",
            candidate_limit=self._policy.detail_candidate_limit(request.limit),
            result_limit=request.limit,
        )

    @classmethod
    def _weighted_terms(
        cls,
        normalization: QueryNormalization,
    ) -> tuple[WeightedTerm, ...]:
        selected: dict[str, WeightedTerm] = {}

        def add(value: str, source: TermSource) -> None:
            text = value.strip().casefold()
            if len(text) < 2 or text in _CHINESE_STOP_TERMS:
                return
            candidate = WeightedTerm(text, source, _TERM_WEIGHTS[source])
            current = selected.get(text)
            if current is None or candidate.weight > current.weight:
                selected[text] = candidate

        for term in normalization.normalized_terms:
            add(term, "canonical")
        for term in _ASCII_TERM_PATTERN.findall(normalization.cleaned_text):
            add(term, "technical")
        if 2 <= len(normalization.cleaned_text) <= 80:
            add(normalization.cleaned_text, "raw_phrase")
        for sequence in _CHINESE_SEQUENCE_PATTERN.findall(normalization.cleaned_text):
            for size in (2, 3, 4):
                if len(sequence) < size:
                    continue
                for index in range(len(sequence) - size + 1):
                    add(sequence[index : index + size], "chinese_fallback")

        return tuple(
            sorted(
                selected.values(),
                key=lambda item: (-item.weight, -len(item.text), item.text),
            )[:200]
        )

    @classmethod
    def _allowed_sources(
        cls,
        request: RetrievalQuery,
        raw_query: str,
    ) -> frozenset[RetrievalSourceType]:
        mapping: dict[str, set[RetrievalSourceType]] = {
            "files": {"file_detail"},
            "specification": {"project_specification"},
            "memory": {"long_term_memory", "short_term_memory"},
            "habits": {"user_habit"},
            "changes": {"update_journal"},
        }
        if request.focus != "auto":
            return frozenset(mapping[request.focus])

        sources: set[RetrievalSourceType] = {
            "file_detail",
            "project_specification",
            "long_term_memory",
            "short_term_memory",
        }
        if cls._contains_hint(raw_query, _HABIT_HINTS):
            sources.add("user_habit")
        if cls._contains_hint(raw_query, _CHANGE_HINTS):
            sources.add("update_journal")
        return frozenset(sources)

    @staticmethod
    def _contains_hint(text: str, hints: tuple[str, ...]) -> bool:
        lowered = text.casefold()
        return any(hint.casefold() in lowered for hint in hints)

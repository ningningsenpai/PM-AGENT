"""用户问题归一化和召回意图判断。"""
from __future__ import annotations

from dataclasses import dataclass
import re

from app.input_context.normalization import (
    LexiconLoadError,
    NormalizationService,
    TextNormalizer,
)
from app.input_context.retrieval.schemas import RetrievalQuery

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


@dataclass(frozen=True, slots=True)
class QueryAnalysis:
    """归一化后供候选生成和排序共同使用的问题信息。"""

    raw_query: str
    normalized_terms: tuple[str, ...]
    include_habits: bool
    include_changes: bool
    read_source: bool


class RetrievalQueryAnalyzer:
    """集中处理词项扩展和轻量召回意图，不访问项目数据。"""

    def __init__(self, normalization: NormalizationService) -> None:
        self._normalization = normalization
        self._text_normalizer = TextNormalizer()

    def analyze(
        self,
        request: RetrievalQuery,
        project_id: int,
        warnings: list[str],
    ) -> QueryAnalysis:
        normalized_terms: list[str] = []
        try:
            normalized = self._normalization.normalize_query(
                request.query,
                project_id=str(project_id),
            )
            cleaned = normalized.cleaned_text
            normalized_terms.extend(normalized.normalized_terms)
        except (LexiconLoadError, OSError, ValueError):
            cleaned = self._text_normalizer.normalize_for_matching(request.query)
            warnings.append("项目词库不可用，已退化为基础文本归一化")

        terms = set(normalized_terms)
        terms.update(_ASCII_TERM_PATTERN.findall(cleaned))
        for sequence in _CHINESE_SEQUENCE_PATTERN.findall(cleaned):
            for size in (2, 3, 4):
                if len(sequence) < size:
                    continue
                terms.update(
                    sequence[index : index + size]
                    for index in range(len(sequence) - size + 1)
                )
        terms.difference_update(_CHINESE_STOP_TERMS)
        normalized_query_terms = tuple(
            sorted(
                {
                    term.strip().casefold()
                    for term in terms
                    if len(term.strip()) >= 2
                },
                key=lambda item: (-len(item), item),
            )[:200]
        )
        return QueryAnalysis(
            raw_query=request.query,
            normalized_terms=normalized_query_terms,
            include_habits=(
                request.focus == "habits"
                or (
                    request.focus == "auto"
                    and self.contains_hint(request.query, _HABIT_HINTS)
                )
            ),
            include_changes=(
                request.focus == "changes"
                or (
                    request.focus == "auto"
                    and self.contains_hint(request.query, _CHANGE_HINTS)
                )
            ),
            read_source=(
                request.evidence_level == "source"
                or (
                    request.evidence_level == "auto"
                    and self.contains_hint(request.query, _SOURCE_EVIDENCE_HINTS)
                )
            ),
        )

    @staticmethod
    def contains_hint(text: str, hints: tuple[str, ...]) -> bool:
        lowered = text.casefold()
        return any(hint.casefold() in lowered for hint in hints)

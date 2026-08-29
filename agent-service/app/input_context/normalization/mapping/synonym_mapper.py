"""别名到标准术语的归一化映射。"""

from __future__ import annotations

from app.input_context.normalization.matching import AhoCandidate
from app.input_context.normalization.preprocessing import TextNormalizationResult
from app.input_context.normalization.schemas import TermMatch

__all__ = ["SynonymMapper"]


class SynonymMapper:
    """把已消歧候选映射为标准术语并恢复原文位置。"""

    @staticmethod
    def map_matches(
        raw_text: str,
        normalized_text: TextNormalizationResult,
        candidates: tuple[AhoCandidate, ...],
    ) -> tuple[TermMatch, ...]:
        """根据清洗字符位置映射生成用户可追踪的命中结果。"""
        matches: list[TermMatch] = []
        for candidate in candidates:
            raw_start = normalized_text.original_index_map[candidate.cleaned_start]
            raw_end = normalized_text.original_index_map[candidate.cleaned_end]
            entry = candidate.entry
            matches.append(
                TermMatch(
                    term_id=entry.term_id,
                    canonical=entry.canonical,
                    alias=candidate.alias,
                    matched_text=raw_text[raw_start : raw_end + 1],
                    category=entry.category,
                    tags=entry.tags,
                    start=raw_start,
                    end=raw_end,
                    cleaned_start=candidate.cleaned_start,
                    cleaned_end=candidate.cleaned_end,
                    source=entry.source,
                    lexicon_id=entry.lexicon_id,
                    scope=entry.scope,
                )
            )
        return tuple(matches)

    @staticmethod
    def collect_normalized_terms(matches: tuple[TermMatch, ...]) -> tuple[str, ...]:
        """按首次出现顺序生成不重复的标准术语集合。"""
        terms: list[str] = []
        seen_terms: set[str] = set()
        for match in matches:
            if match.canonical in seen_terms:
                continue
            seen_terms.add(match.canonical)
            terms.append(match.canonical)
        return tuple(terms)

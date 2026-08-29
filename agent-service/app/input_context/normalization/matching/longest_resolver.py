"""基于候选命中的最长正向匹配消歧器。"""

from __future__ import annotations

from app.input_context.normalization.lexicon.models import LexiconScope
from app.input_context.normalization.matching.aho_matcher import AhoCandidate

__all__ = ["LongestMatchResolver"]


_SCOPE_RANK = {
    LexiconScope.COMMON: 0,
    LexiconScope.DOMAIN: 1,
    LexiconScope.PROJECT: 2,
}


class LongestMatchResolver:
    """按位置、长度、作用域和优先级选择不重叠候选。"""

    @staticmethod
    def resolve(candidates: tuple[AhoCandidate, ...]) -> tuple[AhoCandidate, ...]:
        """实现候选集上的最长正向匹配策略。"""
        selected: list[AhoCandidate] = []
        occupied_positions: set[int] = set()
        ordered_candidates = sorted(
            candidates,
            key=lambda item: (
                item.cleaned_start,
                -(item.cleaned_end - item.cleaned_start + 1),
                -_SCOPE_RANK[item.entry.scope],
                -item.entry.priority,
                item.entry.term_id,
            ),
        )

        for candidate in ordered_candidates:
            span = set(range(candidate.cleaned_start, candidate.cleaned_end + 1))
            if occupied_positions.intersection(span):
                continue
            selected.append(candidate)
            occupied_positions.update(span)

        return tuple(selected)

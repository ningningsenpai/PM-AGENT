"""字段加权排序和详情切片定位。"""
from __future__ import annotations

from typing import Any

from app.input_context.normalization import TextNormalizer
from app.input_context.retrieval.candidate import RetrievalCandidate
from app.project_context.file_detail.schemas import FileDetail


class RetrievalRanker:
    """提供无状态、可解释的词法评分规则。"""

    def __init__(self) -> None:
        self._text_normalizer = TextNormalizer()

    def score_all(
        self,
        candidates: list[RetrievalCandidate],
        raw_query: str,
        terms: tuple[str, ...],
    ) -> list[RetrievalCandidate]:
        for candidate in candidates:
            candidate.score = self.score(candidate, raw_query, terms)
        return self.sort([item for item in candidates if item.score > 0])

    def score(
        self,
        candidate: RetrievalCandidate,
        raw_query: str,
        terms: tuple[str, ...],
    ) -> float:
        high = self._normalized_fields(candidate.high_fields)
        medium = self._normalized_fields(candidate.medium_fields)
        low = self._normalized_fields(candidate.low_fields)
        score = self._field_score(terms, high, 6.0)
        score += self._field_score(terms, medium, 3.0)
        score += self._field_score(terms, low, 1.0)
        cleaned_query = self._text_normalizer.normalize_for_matching(raw_query)
        if len(cleaned_query) >= 2 and any(
            cleaned_query in field for field in [*high, *medium]
        ):
            score += 8.0
        if score > 0 and candidate.importance == "high":
            score += 1.0
        return round(score, 4)

    def best_source_range(
        self,
        detail: FileDetail,
        raw_query: str,
        terms: tuple[str, ...],
    ) -> tuple[int, int] | None:
        best: tuple[float, int, int] | None = None
        for item in detail.content_slices:
            if not isinstance(item, dict):
                continue
            source_range = item.get("source_range")
            if not isinstance(source_range, dict):
                continue
            start_line = source_range.get("start_line")
            end_line = source_range.get("end_line")
            if not isinstance(start_line, int) or not isinstance(end_line, int):
                continue
            primary_fields = self._normalized_fields(
                self.strings(
                    [
                        item.get("summary"),
                        item.get("entities"),
                        item.get("slice_id"),
                        item.get("type"),
                    ]
                )
            )
            keyword_fields = self._normalized_fields(
                self.strings(item.get("keywords"))
            )
            score = self._field_score(terms, primary_fields, 4.0)
            score += self._field_score(terms, keyword_fields, 1.0)
            cleaned_query = self._text_normalizer.normalize_for_matching(raw_query)
            if len(cleaned_query) >= 2 and any(
                cleaned_query in field for field in primary_fields
            ):
                score += 8.0
            current = (score, start_line, end_line)
            if best is None or current[0] > best[0]:
                best = current
        return None if best is None else (best[1], best[2])

    @staticmethod
    def sort(candidates: list[RetrievalCandidate]) -> list[RetrievalCandidate]:
        return sorted(candidates, key=RetrievalRanker.sort_key, reverse=True)

    @staticmethod
    def sort_key(candidate: RetrievalCandidate) -> tuple[float, int, str]:
        priority = {
            "source_file": 4,
            "file_detail": 3,
            "project_specification": 2,
            "short_term_memory": 1,
            "long_term_memory": 1,
            "user_habit": 0,
            "update_journal": 0,
        }.get(candidate.source_type, 0)
        return candidate.score, priority, candidate.source_id

    @staticmethod
    def _field_score(
        terms: tuple[str, ...],
        fields: list[str],
        weight: float,
    ) -> float:
        matched = {term for term in terms if any(term in field for field in fields)}
        return sum(weight * min(len(term), 8) / 4 for term in matched)

    def _normalized_fields(self, fields: list[str]) -> list[str]:
        return [
            self._text_normalizer.normalize_for_matching(field)
            for field in fields
            if field.strip()
        ]

    @classmethod
    def strings(cls, value: Any) -> list[str]:
        if isinstance(value, str):
            return [value]
        if isinstance(value, dict):
            result: list[str] = []
            for nested in value.values():
                result.extend(cls.strings(nested))
            return result
        if isinstance(value, list):
            result = []
            for nested in value:
                result.extend(cls.strings(nested))
            return result
        return []

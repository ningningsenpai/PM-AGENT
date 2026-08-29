"""内容归一化处理流水线编排。"""

from __future__ import annotations

from time import perf_counter

from app.input_context.normalization.mapping import SynonymMapper
from app.input_context.normalization.matching import (
    AhoMatcher,
    CompiledLexicon,
    LongestMatchResolver,
)
from app.input_context.normalization.preprocessing import TextNormalizer
from app.input_context.normalization.schemas import NormalizationResult

__all__ = ["NormalizationPipeline"]


class NormalizationPipeline:
    """以固定顺序执行文本处理、候选匹配、消歧和术语映射。"""

    def __init__(
        self,
        text_normalizer: TextNormalizer,
        matcher: AhoMatcher,
        resolver: LongestMatchResolver,
        synonym_mapper: SynonymMapper,
    ) -> None:
        self.text_normalizer = text_normalizer
        self.matcher = matcher
        self.resolver = resolver
        self.synonym_mapper = synonym_mapper

    def run(self, text: str, compiled_lexicon: CompiledLexicon) -> NormalizationResult:
        """运行完整归一化流水线并记录各阶段耗时。"""
        total_started_at = perf_counter()

        stage_started_at = perf_counter()
        normalized_text = self.text_normalizer.normalize(text)
        preprocessing_ms = self._elapsed_ms(stage_started_at)

        stage_started_at = perf_counter()
        candidates = self.matcher.match(normalized_text.cleaned_text, compiled_lexicon)
        matching_ms = self._elapsed_ms(stage_started_at)

        stage_started_at = perf_counter()
        selected_candidates = self.resolver.resolve(candidates)
        resolving_ms = self._elapsed_ms(stage_started_at)

        stage_started_at = perf_counter()
        matches = self.synonym_mapper.map_matches(
            text, normalized_text, selected_candidates
        )
        normalized_terms = self.synonym_mapper.collect_normalized_terms(matches)
        mapping_ms = self._elapsed_ms(stage_started_at)

        return NormalizationResult(
            raw_text=text,
            cleaned_text=normalized_text.cleaned_text,
            lexicon_version_set=compiled_lexicon.merged_lexicon.version_set,
            normalized_terms=normalized_terms,
            matches=matches,
            warnings=(),
            stage_durations_ms={
                "preprocessing": preprocessing_ms,
                "matching": matching_ms,
                "resolving": resolving_ms,
                "mapping": mapping_ms,
                "total": self._elapsed_ms(total_started_at),
            },
        )

    @staticmethod
    def _elapsed_ms(started_at: float) -> float:
        return round((perf_counter() - started_at) * 1000, 4)

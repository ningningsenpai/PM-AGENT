"""Aho-Corasick 多模式术语匹配器。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import ahocorasick

from app.normalization.lexicon.models import MergedLexicon, ResolvedLexiconEntry
from app.normalization.preprocessing import TextNormalizer

__all__ = ["AhoCandidate", "AhoMatcher", "CompiledLexicon"]


@dataclass(frozen=True)
class AhoCandidate:
    """自动机扫描产生的原始候选。"""

    entry: ResolvedLexiconEntry
    alias: str
    normalized_alias: str
    cleaned_start: int
    cleaned_end: int


@dataclass(frozen=True)
class CompiledLexicon:
    """可复用的只读自动机及其合并词库信息。"""

    merged_lexicon: MergedLexicon
    automaton: Any


class AhoMatcher:
    """构建并扫描 Aho-Corasick 多模式匹配自动机。"""

    def __init__(self, text_normalizer: TextNormalizer) -> None:
        self.text_normalizer = text_normalizer

    def compile(self, merged_lexicon: MergedLexicon) -> CompiledLexicon:
        """把已校验的合并词库编译成只读自动机。"""
        automaton = ahocorasick.Automaton()
        registered_aliases: dict[str, str] = {}

        for entry in merged_lexicon.entries:
            for alias in entry.aliases:
                normalized_alias = self.text_normalizer.normalize_for_matching(alias)
                existing_term_id = registered_aliases.get(normalized_alias)
                if existing_term_id is not None and existing_term_id != entry.term_id:
                    raise ValueError(f"自动机构建发现未处理的别名冲突：{alias}")
                if existing_term_id == entry.term_id:
                    continue
                registered_aliases[normalized_alias] = entry.term_id
                automaton.add_word(normalized_alias, (entry, alias, normalized_alias))

        automaton.make_automaton()
        return CompiledLexicon(merged_lexicon=merged_lexicon, automaton=automaton)

    @staticmethod
    def match(cleaned_text: str, compiled_lexicon: CompiledLexicon) -> tuple[AhoCandidate, ...]:
        """扫描清洗后的文本并返回全部候选命中。"""
        candidates: list[AhoCandidate] = []
        for cleaned_end, payload in compiled_lexicon.automaton.iter(cleaned_text):
            entry, alias, normalized_alias = payload
            cleaned_start = cleaned_end - len(normalized_alias) + 1
            candidates.append(
                AhoCandidate(
                    entry=entry,
                    alias=alias,
                    normalized_alias=normalized_alias,
                    cleaned_start=cleaned_start,
                    cleaned_end=cleaned_end,
                )
            )
        return tuple(candidates)

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import ahocorasick


DEFAULT_LEXICON_PATH = Path(__file__).with_name("lexicon.json")


@dataclass(frozen=True)
class LexiconEntry:
    canonical: str
    aliases: tuple[str, ...]
    category: str
    tags: tuple[str, ...]


@dataclass(frozen=True)
class MatchResult:
    canonical: str
    alias: str
    category: str
    tags: tuple[str, ...]
    start: int
    end: int


def load_lexicon(path: Path = DEFAULT_LEXICON_PATH) -> list[LexiconEntry]:
    data = json.loads(path.read_text(encoding="utf-8"))
    entries: list[LexiconEntry] = []
    for item in data["entries"]:
        aliases = tuple(dict.fromkeys([item["canonical"], *item.get("aliases", [])]))
        entries.append(
            LexiconEntry(
                canonical=item["canonical"],
                aliases=aliases,
                category=item.get("category", "unknown"),
                tags=tuple(item.get("tags", [])),
            )
        )
    return entries


def build_automaton(entries: list[LexiconEntry]) -> Any:
    automaton = ahocorasick.Automaton()
    for entry in entries:
        for alias in entry.aliases:
            key = alias.lower()
            payload = {
                "canonical": entry.canonical,
                "alias": alias,
                "category": entry.category,
                "tags": entry.tags,
            }
            automaton.add_word(key, payload)
    automaton.make_automaton()
    return automaton


def match_text(text: str, entries: list[LexiconEntry] | None = None) -> list[MatchResult]:
    lexicon_entries = entries or load_lexicon()
    automaton = build_automaton(lexicon_entries)
    normalized_text = text.lower()
    matches: list[MatchResult] = []

    for end, payload in automaton.iter(normalized_text):
        alias = payload["alias"]
        start = end - len(alias) + 1
        matches.append(
            MatchResult(
                canonical=payload["canonical"],
                alias=alias,
                category=payload["category"],
                tags=tuple(payload["tags"]),
                start=start,
                end=end,
            )
        )

    return dedupe_matches(matches)


def dedupe_matches(matches: list[MatchResult]) -> list[MatchResult]:
    selected: list[MatchResult] = []
    occupied: set[int] = set()

    for item in sorted(matches, key=lambda match: (match.start, -(match.end - match.start), match.canonical)):
        span = set(range(item.start, item.end + 1))
        if occupied.intersection(span):
            continue
        selected.append(item)
        occupied.update(span)

    result: list[MatchResult] = []
    seen_canonical: set[str] = set()
    for item in selected:
        if item.canonical in seen_canonical:
            continue
        result.append(item)
        seen_canonical.add(item.canonical)
    return result


def normalize_text(text: str) -> dict[str, Any]:
    matches = match_text(text)
    return {
        "raw_text": text,
        "normalized_terms": [item.canonical for item in matches],
        "matches": [
            {
                "canonical": item.canonical,
                "alias": item.alias,
                "category": item.category,
                "tags": list(item.tags),
                "start": item.start,
                "end": item.end,
            }
            for item in matches
        ],
    }


def main() -> None:
    text = "帮我看看登录接口是不是少了权限校验，逾期任务会不会带来风险提示"
    print(json.dumps(normalize_text(text), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

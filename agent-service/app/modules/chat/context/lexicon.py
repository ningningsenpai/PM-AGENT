"""复用现有 Aho-Corasick 与最长匹配，按用户、项目及有效版本缓存词库。"""

import hashlib
import json
from functools import lru_cache

from app.input_context.normalization.lexicon.models import (
    LexiconVersionSet,
    MergedLexicon,
    ResolvedLexiconEntry,
)
from app.input_context.normalization.matching.aho_matcher import AhoMatcher
from app.input_context.normalization.matching.longest_resolver import (
    LongestMatchResolver,
)
from app.input_context.normalization.preprocessing import TextNormalizer


@lru_cache(maxsize=64)
def compile_entries(user_id, project_id, payload):
    normalizer = TextNormalizer()
    values = json.loads(payload)
    aliases, conflicts = {}, set()
    for value in values:
        for alias in value["attributes"].get("aliases", []):
            normalized = normalizer.normalize_for_matching(alias)
            if not normalized:
                continue
            canonical = value["attributes"].get("canonical")
            if normalized in aliases and aliases[normalized][0] != canonical:
                conflicts.add(normalized)
            aliases[normalized] = (canonical, alias, value)
    entries = []
    for normalized, (canonical, alias, value) in aliases.items():
        if normalized in conflicts or not canonical:
            continue
        entries.append(
            ResolvedLexiconEntry(
                term_id=f"{value['id']}:{normalized}",
                canonical=canonical,
                aliases=(alias,),
                category="用户词条",
                tags=(),
                priority=0,
                source=f"message:{value['sourceMessageId']}",
                lexicon_id=f"user:{user_id}:project:{project_id}",
                scope="project",
                scope_id=str(project_id),
            )
        )
    if not entries:
        return None
    version = hashlib.sha256(payload.encode()).hexdigest()
    merged = MergedLexicon(
        entries=tuple(entries),
        version_set=LexiconVersionSet(
            common_lexicon_id="learned",
            common_version=version,
            domain_lexicon_id="learned",
            domain_version=version,
            merged_fingerprint=version,
        ),
    )
    return AhoMatcher(normalizer).compile(merged)


def learned_terms(user_id, project_id, query, entries):
    # 条件词条不参与无条件改写；条件判断留给携带完整条目的问答与澄清流程。
    values = [entry for entry in entries if entry["kind"] == "term" and not entry.get("conditions")]
    compiled = compile_entries(
        user_id, project_id, json.dumps(values, ensure_ascii=False, sort_keys=True)
    )
    if compiled is None:
        return []
    candidates = AhoMatcher.match(
        TextNormalizer().normalize_for_matching(query), compiled
    )
    return list(
        dict.fromkeys(
            match.entry.canonical for match in LongestMatchResolver.resolve(candidates)
        )
    )

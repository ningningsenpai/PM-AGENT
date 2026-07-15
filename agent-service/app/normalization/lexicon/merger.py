"""公共、业务和项目术语库的合并策略。"""
from __future__ import annotations

import hashlib
import json

from app.normalization.lexicon.models import (
    LexiconManifest,
    LexiconOverrideRecord,
    LexiconScope,
    LexiconVersionSet,
    MergedLexicon,
    ResolvedLexiconEntry,
)
from app.normalization.preprocessing import TextNormalizer

__all__ = ["LexiconMergeError", "LexiconMerger"]


_SCOPE_RANK = {
    LexiconScope.COMMON: 0,
    LexiconScope.DOMAIN: 1,
    LexiconScope.PROJECT: 2,
}


class LexiconMergeError(RuntimeError):
    """三级词库无法按照显式规则合并。"""


class LexiconMerger:
    """按照公共、业务、项目的优先级生成唯一运行时词库。"""

    def __init__(self, text_normalizer: TextNormalizer) -> None:
        self.text_normalizer = text_normalizer

    def merge(
        self,
        common_manifest: LexiconManifest,
        domain_manifest: LexiconManifest,
        project_manifest: LexiconManifest | None = None,
    ) -> MergedLexicon:
        """合并三级词库并为最终内容生成稳定指纹。"""
        manifests = [common_manifest, domain_manifest]
        if project_manifest is not None:
            manifests.append(project_manifest)
        manifests.sort(key=lambda item: _SCOPE_RANK[item.scope])

        entries_by_term_id = self._merge_same_terms(manifests)
        resolved_entries, override_records = self._resolve_alias_conflicts(entries_by_term_id)
        fingerprint = self._build_fingerprint(manifests, resolved_entries)
        version_set = LexiconVersionSet(
            common_lexicon_id=common_manifest.lexicon_id,
            common_version=common_manifest.version,
            domain_lexicon_id=domain_manifest.lexicon_id,
            domain_version=domain_manifest.version,
            project_lexicon_id=project_manifest.lexicon_id if project_manifest else None,
            project_version=project_manifest.version if project_manifest else None,
            merged_fingerprint=fingerprint,
        )
        return MergedLexicon(
            entries=tuple(sorted(resolved_entries, key=lambda item: item.term_id)),
            version_set=version_set,
            override_records=tuple(override_records),
        )

    def _merge_same_terms(
        self,
        manifests: list[LexiconManifest],
    ) -> dict[str, ResolvedLexiconEntry]:
        entries_by_term_id: dict[str, ResolvedLexiconEntry] = {}
        for manifest in manifests:
            for entry in manifest.entries:
                if not entry.enabled:
                    continue
                resolved_entry = ResolvedLexiconEntry(
                    term_id=entry.term_id,
                    canonical=entry.canonical,
                    aliases=self._unique_aliases((entry.canonical, *entry.aliases)),
                    category=entry.category,
                    tags=tuple(dict.fromkeys(entry.tags)),
                    priority=entry.priority,
                    source=entry.source,
                    override_term_id=entry.override_term_id,
                    lexicon_id=manifest.lexicon_id,
                    scope=manifest.scope,
                    scope_id=manifest.scope_id,
                )
                existing = entries_by_term_id.get(entry.term_id)
                if existing is None:
                    entries_by_term_id[entry.term_id] = resolved_entry
                    continue
                if self._normalize(existing.canonical) != self._normalize(entry.canonical):
                    raise LexiconMergeError(
                        f"词条 {entry.term_id} 在不同词库中使用了不同标准术语"
                    )

                entries_by_term_id[entry.term_id] = resolved_entry.model_copy(
                    update={
                        "aliases": self._unique_aliases((*existing.aliases, *resolved_entry.aliases)),
                        "tags": tuple(dict.fromkeys((*existing.tags, *resolved_entry.tags))),
                        "priority": max(existing.priority, resolved_entry.priority),
                    }
                )
        return entries_by_term_id

    def _resolve_alias_conflicts(
        self,
        entries_by_term_id: dict[str, ResolvedLexiconEntry],
    ) -> tuple[list[ResolvedLexiconEntry], list[LexiconOverrideRecord]]:
        ordered_entries = sorted(
            entries_by_term_id.values(),
            key=lambda item: (_SCOPE_RANK[item.scope], item.priority, item.term_id),
        )
        aliases_by_term_id = {entry.term_id: list(entry.aliases) for entry in ordered_entries}
        alias_owners: dict[str, str] = {}
        override_records: list[LexiconOverrideRecord] = []
        applied_override_term_ids: set[str] = set()

        for entry in ordered_entries:
            if entry.override_term_id is not None and entry.override_term_id not in entries_by_term_id:
                raise LexiconMergeError(
                    f"词条 {entry.term_id} 声明的覆盖目标 {entry.override_term_id} 不存在"
                )

        for entry in ordered_entries:
            for alias in tuple(aliases_by_term_id[entry.term_id]):
                normalized_alias = self._normalize(alias)
                owner_term_id = alias_owners.get(normalized_alias)
                if owner_term_id is None or owner_term_id == entry.term_id:
                    alias_owners[normalized_alias] = entry.term_id
                    continue

                owner = entries_by_term_id[owner_term_id]
                if self._normalize(owner.canonical) == self._normalize(entry.canonical):
                    raise LexiconMergeError(
                        f"标准术语 {entry.canonical} 使用了多个 term_id：{owner_term_id}、{entry.term_id}"
                    )
                if entry.override_term_id != owner_term_id:
                    raise LexiconMergeError(
                        f"别名 {alias} 同时映射到 {owner.canonical} 和 {entry.canonical}，且未声明显式覆盖"
                    )

                aliases_by_term_id[owner_term_id] = [
                    item
                    for item in aliases_by_term_id[owner_term_id]
                    if self._normalize(item) != normalized_alias
                ]
                alias_owners[normalized_alias] = entry.term_id
                override_records.append(
                    LexiconOverrideRecord(
                        alias=alias,
                        overridden_term_id=owner_term_id,
                        overriding_term_id=entry.term_id,
                        overriding_scope=entry.scope,
                    )
                )
                applied_override_term_ids.add(entry.term_id)

        for entry in ordered_entries:
            if entry.override_term_id is not None and entry.term_id not in applied_override_term_ids:
                raise LexiconMergeError(
                    f"词条 {entry.term_id} 声明了覆盖目标，但没有覆盖任何冲突别名"
                )

        resolved_entries = [
            entry.model_copy(update={"aliases": tuple(aliases_by_term_id[entry.term_id])})
            for entry in ordered_entries
            if aliases_by_term_id[entry.term_id]
        ]
        return resolved_entries, override_records

    def _unique_aliases(self, aliases: tuple[str, ...]) -> tuple[str, ...]:
        unique_aliases: list[str] = []
        normalized_aliases: set[str] = set()
        for alias in aliases:
            normalized_alias = self._normalize(alias)
            if not normalized_alias or normalized_alias in normalized_aliases:
                continue
            normalized_aliases.add(normalized_alias)
            unique_aliases.append(alias)
        return tuple(unique_aliases)

    def _normalize(self, text: str) -> str:
        return self.text_normalizer.normalize_for_matching(text)

    @staticmethod
    def _build_fingerprint(
        manifests: list[LexiconManifest],
        entries: list[ResolvedLexiconEntry],
    ) -> str:
        fingerprint_payload = {
            "sources": [
                {
                    "lexicon_id": item.lexicon_id,
                    "version": item.version,
                    "scope": item.scope.value,
                    "scope_id": item.scope_id,
                }
                for item in manifests
            ],
            "entries": [
                item.model_dump(mode="json")
                for item in sorted(entries, key=lambda entry: entry.term_id)
            ],
        }
        encoded_payload = json.dumps(
            fingerprint_payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded_payload).hexdigest()

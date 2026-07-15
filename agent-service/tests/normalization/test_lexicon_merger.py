"""三级术语库合并测试。"""
from __future__ import annotations

import unittest

from app.normalization.lexicon.merger import LexiconMergeError, LexiconMerger
from app.normalization.lexicon.models import (
    LexiconEntry,
    LexiconManifest,
    LexiconScope,
    LexiconStatus,
)
from app.normalization.preprocessing import TextNormalizer


class LexiconMergerTest(unittest.TestCase):
    """验证冲突阻断和项目词显式覆盖。"""

    def setUp(self) -> None:
        self.merger = LexiconMerger(TextNormalizer())
        self.domain_manifest = self._manifest("domain", LexiconScope.DOMAIN, tuple())

    def test_reject_alias_conflict_without_override(self) -> None:
        common = self._manifest(
            "common",
            LexiconScope.COMMON,
            (self._entry("common-board", "公共看板", ("看板",)),),
        )
        project = self._manifest(
            "project-1",
            LexiconScope.PROJECT,
            (self._entry("project-board", "项目看板", ("看板",)),),
            scope_id="1",
        )

        with self.assertRaisesRegex(LexiconMergeError, "未声明显式覆盖"):
            self.merger.merge(common, self.domain_manifest, project)

    def test_allow_explicit_project_override(self) -> None:
        common = self._manifest(
            "common",
            LexiconScope.COMMON,
            (self._entry("common-board", "公共看板", ("看板",)),),
        )
        project = self._manifest(
            "project-1",
            LexiconScope.PROJECT,
            (
                self._entry(
                    "project-board",
                    "项目看板",
                    ("看板",),
                    override_term_id="common-board",
                ),
            ),
            scope_id="1",
        )

        merged = self.merger.merge(common, self.domain_manifest, project)
        project_entry = next(item for item in merged.entries if item.term_id == "project-board")

        self.assertIn("看板", project_entry.aliases)
        self.assertEqual(1, len(merged.override_records))
        self.assertEqual(64, len(merged.version_set.merged_fingerprint))

    def test_reject_missing_override_target(self) -> None:
        common = self._manifest("common", LexiconScope.COMMON, tuple())
        project = self._manifest(
            "project-1",
            LexiconScope.PROJECT,
            (
                self._entry(
                    "project-board",
                    "项目看板",
                    ("看板",),
                    override_term_id="missing-term",
                ),
            ),
            scope_id="1",
        )

        with self.assertRaisesRegex(LexiconMergeError, "覆盖目标 missing-term 不存在"):
            self.merger.merge(common, self.domain_manifest, project)

    @staticmethod
    def _entry(
        term_id: str,
        canonical: str,
        aliases: tuple[str, ...],
        *,
        override_term_id: str | None = None,
    ) -> LexiconEntry:
        return LexiconEntry(
            term_id=term_id,
            canonical=canonical,
            aliases=aliases,
            category="test",
            source="manual",
            override_term_id=override_term_id,
        )

    @staticmethod
    def _manifest(
        lexicon_id: str,
        scope: LexiconScope,
        entries: tuple[LexiconEntry, ...],
        *,
        scope_id: str | None = None,
    ) -> LexiconManifest:
        return LexiconManifest(
            lexicon_id=lexicon_id,
            version="1.0.0",
            scope=scope,
            scope_id=scope_id,
            status=LexiconStatus.PUBLISHED,
            description="测试词库",
            entries=entries,
        )


if __name__ == "__main__":
    unittest.main()

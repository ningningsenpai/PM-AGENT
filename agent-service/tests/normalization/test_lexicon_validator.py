"""术语库校验测试。"""
from __future__ import annotations

import unittest

from app.normalization.lexicon.models import (
    LexiconEntry,
    LexiconManifest,
    LexiconScope,
    LexiconStatus,
)
from app.normalization.lexicon.validator import LexiconValidator
from app.normalization.preprocessing import TextNormalizer


class LexiconValidatorTest(unittest.TestCase):
    """验证歧义别名和发布状态检查。"""

    def setUp(self) -> None:
        self.validator = LexiconValidator(TextNormalizer())

    def test_detect_ambiguous_alias(self) -> None:
        manifest = LexiconManifest(
            lexicon_id="test-common",
            version="1.0.0",
            scope=LexiconScope.COMMON,
            status=LexiconStatus.PUBLISHED,
            description="测试词库",
            entries=(
                self._entry("term-a", "认证", ("权限校验",)),
                self._entry("term-b", "授权", ("权限校验",)),
            ),
        )

        report = self.validator.validate_manifest(manifest, require_published=True)

        self.assertTrue(report.has_errors)
        self.assertIn("ambiguous_alias", {item.code for item in report.errors})

    def test_reject_draft_at_runtime(self) -> None:
        manifest = LexiconManifest(
            lexicon_id="test-common",
            version="draft",
            scope=LexiconScope.COMMON,
            status=LexiconStatus.DRAFT,
            description="测试词库",
            entries=(self._entry("term-a", "认证", tuple()),),
        )

        report = self.validator.validate_manifest(manifest, require_published=True)

        self.assertIn("unpublished_lexicon", {item.code for item in report.errors})

    @staticmethod
    def _entry(term_id: str, canonical: str, aliases: tuple[str, ...]) -> LexiconEntry:
        return LexiconEntry(
            term_id=term_id,
            canonical=canonical,
            aliases=aliases,
            category="test",
            source="manual",
        )


if __name__ == "__main__":
    unittest.main()

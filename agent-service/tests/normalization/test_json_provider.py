"""JSON 术语库来源测试。"""
from __future__ import annotations

import unittest

from app.normalization.lexicon.json_provider import JsonLexiconProvider, LexiconLoadError
from app.normalization.lexicon.models import LexiconScope, LexiconStatus


class JsonLexiconProviderTest(unittest.TestCase):
    """验证正式资源加载和文件标识边界。"""

    def test_load_published_manifests(self) -> None:
        provider = JsonLexiconProvider()

        common_manifest = provider.load_common()
        domain_manifest = provider.load_domain("project_management")

        self.assertIs(LexiconScope.COMMON, common_manifest.scope)
        self.assertIs(LexiconScope.DOMAIN, domain_manifest.scope)
        self.assertIs(LexiconStatus.PUBLISHED, common_manifest.status)
        self.assertGreater(len(common_manifest.entries), 0)
        self.assertGreater(len(domain_manifest.entries), 0)

    def test_reject_unsafe_domain_identifier(self) -> None:
        provider = JsonLexiconProvider()

        with self.assertRaisesRegex(LexiconLoadError, "业务域标识"):
            provider.load_domain("../secret")


if __name__ == "__main__":
    unittest.main()

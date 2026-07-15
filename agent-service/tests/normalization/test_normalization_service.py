"""内容归一化服务测试。"""
from __future__ import annotations

import unittest

from app.normalization import create_default_normalization_service


class NormalizationServiceTest(unittest.TestCase):
    """验证公开入口、最长词优先、位置和缓存复用。"""

    def setUp(self) -> None:
        self.service = create_default_normalization_service()

    def test_normalize_query_with_aliases(self) -> None:
        result = self.service.normalize_query("登录API缺少ＪＷＴ认证，延期任务需要风险提示")

        self.assertEqual(
            ("登录接口", "认证鉴权", "逾期任务", "风险分析"),
            result.normalized_terms,
        )
        self.assertEqual("登录API", result.matches[0].matched_text)
        self.assertEqual("ＪＷＴ认证", result.matches[1].matched_text)
        self.assertEqual("2026.07.1", result.lexicon_version_set.common_version)

    def test_longest_match_removes_nested_task(self) -> None:
        result = self.service.normalize_query("逾期任务需要重新排期")

        self.assertEqual(("逾期任务",), result.normalized_terms)

    def test_registry_reuses_and_invalidates_compiled_lexicon(self) -> None:
        first = self.service.registry.get_or_build()
        second = self.service.registry.get_or_build()
        self.assertIs(first, second)
        self.assertEqual(1, self.service.registry.cache_size)

        self.service.reload_lexicons()
        third = self.service.registry.get_or_build()

        self.assertIsNot(first, third)
        self.assertEqual(1, self.service.registry.cache_size)


if __name__ == "__main__":
    unittest.main()

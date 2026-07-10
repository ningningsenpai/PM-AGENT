"""基础文本处理测试。"""
from __future__ import annotations

import unittest

from app.normalization.preprocessing import TextNormalizer


class TextNormalizerTest(unittest.TestCase):
    """验证字符清洗和原文位置映射。"""

    def test_normalize_full_width_case_and_whitespace(self) -> None:
        normalizer = TextNormalizer()

        result = normalizer.normalize(" ＡＢＣ\t 权限校验 ")

        self.assertEqual("abc 权限校验", result.cleaned_text)
        self.assertEqual(1, result.original_index_map[0])
        self.assertEqual(9, result.original_index_map[-1])


if __name__ == "__main__":
    unittest.main()

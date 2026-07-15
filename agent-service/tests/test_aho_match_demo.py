import unittest

try:
    import ahocorasick  # noqa: F401
except ModuleNotFoundError:
    ahocorasick = None

from normalization_demo.aho_match_demo import normalize_text
from normalization_demo.evaluate_aho_match import evaluate_all, load_cases


@unittest.skipIf(ahocorasick is None, "缺少 pyahocorasick 依赖，跳过 Aho-Corasick demo 测试")
class AhoMatchDemoTest(unittest.TestCase):
    def test_normalize_text_should_match_canonical_terms(self):
        result = normalize_text("登录接口是不是少了权限校验，延期任务有没有风险候选")

        self.assertEqual(
            result["normalized_terms"],
            ["登录接口", "认证鉴权", "逾期任务", "风险分析"],
        )

    def test_evaluation_cases_should_have_full_recall(self):
        report = evaluate_all(load_cases())

        self.assertEqual(report["summary"]["recall"], 1.0)
        self.assertEqual(report["summary"]["precision"], 1.0)


if __name__ == "__main__":
    unittest.main()

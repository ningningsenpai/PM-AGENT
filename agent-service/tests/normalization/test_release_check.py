"""术语库发布闸门测试。"""
from __future__ import annotations

import unittest

from eval.normalization.release_check import run_release_check


class ReleaseCheckTest(unittest.TestCase):
    """验证正式词库能够通过结构和效果闸门。"""

    def test_release_check_passes(self) -> None:
        report = run_release_check()

        self.assertTrue(report["ready_for_publish"])
        self.assertEqual(1.0, report["evaluation"]["summary"]["precision"])
        self.assertEqual(1.0, report["evaluation"]["summary"]["recall"])


if __name__ == "__main__":
    unittest.main()

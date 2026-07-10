from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from normalization_demo.aho_match_demo import normalize_text


DEFAULT_CASES_PATH = Path(__file__).with_name("evaluation_cases.json")


def load_cases(path: Path = DEFAULT_CASES_PATH) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def evaluate_case(case: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_text(case["text"])
    expected = set(case["expected_canonical"])
    predicted = set(normalized["normalized_terms"])
    hit = expected.intersection(predicted)
    missed = expected - predicted
    extra = predicted - expected

    precision = len(hit) / len(predicted) if predicted else 0.0
    recall = len(hit) / len(expected) if expected else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0

    return {
        "id": case["id"],
        "text": case["text"],
        "expected": sorted(expected),
        "predicted": sorted(predicted),
        "hit": sorted(hit),
        "missed": sorted(missed),
        "extra": sorted(extra),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "matches": normalized["matches"],
    }


def evaluate_all(cases: list[dict[str, Any]]) -> dict[str, Any]:
    results = [evaluate_case(case) for case in cases]
    total_expected = sum(len(item["expected"]) for item in results)
    total_predicted = sum(len(item["predicted"]) for item in results)
    total_hit = sum(len(item["hit"]) for item in results)

    precision = total_hit / total_predicted if total_predicted else 0.0
    recall = total_hit / total_expected if total_expected else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0

    return {
        "stage": "step_1_aho_corasick_lexicon_match",
        "description": "第一步只评估公共词库精确命中效果，暂不引入分词、同义词扩展、BM25F 或 SimHash。",
        "summary": {
            "case_count": len(results),
            "total_expected": total_expected,
            "total_predicted": total_predicted,
            "total_hit": total_hit,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
        },
        "cases": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="评估 Aho-Corasick 词库匹配 demo")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES_PATH, help="评估用例 JSON 文件路径")
    args = parser.parse_args()

    report = evaluate_all(load_cases(args.cases))
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

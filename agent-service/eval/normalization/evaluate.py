"""内容归一化分阶段离线评估入口。"""
from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from app.normalization import NormalizationResult, create_default_normalization_service

__all__ = ["DEFAULT_CASES_PATH", "evaluate_all", "evaluate_case", "load_cases"]


DEFAULT_CASES_PATH = Path(__file__).with_name("cases.json")
Normalizer = Callable[[str], NormalizationResult]


def load_cases(path: Path = DEFAULT_CASES_PATH) -> list[dict[str, Any]]:
    """加载固定评估样例并检查基础结构。"""
    try:
        raw_cases = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"归一化评估用例无法读取：{path}") from exc
    if not isinstance(raw_cases, list):
        raise ValueError("归一化评估用例必须是 JSON 数组")
    for item in raw_cases:
        if not isinstance(item, dict) or not {"id", "text", "expected_canonical"}.issubset(item):
            raise ValueError("每条评估用例必须包含 id、text 和 expected_canonical")
    return raw_cases


def evaluate_case(case: dict[str, Any], normalizer: Normalizer) -> dict[str, Any]:
    """计算单条样例的命中、漏召、误召和三项基础指标。"""
    normalized = normalizer(case["text"])
    expected = set(case["expected_canonical"])
    predicted = set(normalized.normalized_terms)
    hit = expected.intersection(predicted)
    missed = expected - predicted
    extra = predicted - expected

    precision = len(hit) / len(predicted) if predicted else (1.0 if not expected else 0.0)
    recall = len(hit) / len(expected) if expected else 1.0
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
        "matches": [item.model_dump(mode="json") for item in normalized.matches],
        "stage_durations_ms": normalized.stage_durations_ms,
    }


def evaluate_all(
    cases: list[dict[str, Any]],
    normalizer: Normalizer | None = None,
) -> dict[str, Any]:
    """评估全部样例并计算按命中数量聚合的微平均指标。"""
    if normalizer is None:
        service = create_default_normalization_service()
        normalizer = service.normalize_query

    results = [evaluate_case(case, normalizer) for case in cases]
    total_expected = sum(len(item["expected"]) for item in results)
    total_predicted = sum(len(item["predicted"]) for item in results)
    total_hit = sum(len(item["hit"]) for item in results)
    total_duration_ms = sum(item["stage_durations_ms"].get("total", 0.0) for item in results)

    precision = total_hit / total_predicted if total_predicted else (1.0 if not total_expected else 0.0)
    recall = total_hit / total_expected if total_expected else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0

    return {
        "stage": "normalization_steps_1_to_3",
        "description": "评估 Aho-Corasick、最长匹配和同义词归一化的标准术语效果。",
        "summary": {
            "case_count": len(results),
            "total_expected": total_expected,
            "total_predicted": total_predicted,
            "total_hit": total_hit,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "average_duration_ms": round(total_duration_ms / len(results), 4) if results else 0.0,
        },
        "cases": results,
    }


def main() -> None:
    """运行命令行评估并输出 JSON 报告。"""
    parser = argparse.ArgumentParser(description="评估内容归一化前三阶段效果")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES_PATH, help="评估用例 JSON 文件路径")
    args = parser.parse_args()
    print(json.dumps(evaluate_all(load_cases(args.cases)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

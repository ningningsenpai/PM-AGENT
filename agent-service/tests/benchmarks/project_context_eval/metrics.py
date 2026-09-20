"""检索、拒答、引用与运行成本指标。"""

from __future__ import annotations

import math
from collections import defaultdict
from statistics import mean


def retrieval_metrics(
    ranked_paths: list[str],
    relevance: dict[str, int],
    *,
    cutoffs: tuple[int, ...] = (1, 3, 5, 8),
) -> dict[str, float]:
    total_relevant = len(relevance)
    result: dict[str, float] = {}
    for cutoff in cutoffs:
        hits = len(set(ranked_paths[:cutoff]) & relevance.keys())
        result[f"recall@{cutoff}"] = round(
            hits / total_relevant if total_relevant else 1.0,
            6,
        )
    reciprocal_rank = 0.0
    for rank, path in enumerate(ranked_paths, 1):
        if path in relevance:
            reciprocal_rank = 1 / rank
            break
    result["mrr"] = round(reciprocal_rank if total_relevant else 1.0, 6)
    for cutoff in (5, 8):
        gains = [relevance.get(path, 0) for path in ranked_paths[:cutoff]]
        dcg = sum((2**gain - 1) / math.log2(rank + 1) for rank, gain in enumerate(gains, 1))
        ideal = sorted(relevance.values(), reverse=True)[:cutoff]
        idcg = sum((2**gain - 1) / math.log2(rank + 1) for rank, gain in enumerate(ideal, 1))
        result[f"ndcg@{cutoff}"] = round(dcg / idcg if idcg else 1.0, 6)
    return result


def percentile(values: list[float], percentile_value: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, math.ceil(percentile_value * len(ordered)) - 1)
    return ordered[index]


def aggregate_query_runs(records: list[dict]) -> dict:
    by_algorithm: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        by_algorithm[record["algorithm"]].append(record)
    aggregate = {}
    for algorithm, items in sorted(by_algorithm.items()):
        metric_names = sorted(
            {name for item in items for name in item.get("metrics", {})}
        )
        metrics = {
            name: round(
                mean(
                    float(item["metrics"][name])
                    for item in items
                    if name in item.get("metrics", {})
                ),
                6,
            )
            for name in metric_names
        }
        latencies = [float(item["latency_ms"]) for item in items]
        aggregate[algorithm] = {
            "queryCount": len(items),
            "metrics": metrics,
            "latencyMs": {
                "mean": round(mean(latencies), 4),
                "p95": round(percentile(latencies, 0.95), 4),
            },
            "errors": sum(bool(item.get("error")) for item in items),
        }
    return aggregate

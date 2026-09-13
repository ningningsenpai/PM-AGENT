"""在七轮真实项目快照上对比词法、向量与混合召回。"""

from __future__ import annotations

import argparse
import asyncio
import copy
import json
import math
import re
import time
from collections import Counter
from collections.abc import Callable
from pathlib import Path

from app.core.config import get_settings
from app.infrastructure.storage import StorageLocationFactory, get_object_storage
from app.input_context.normalization import create_default_normalization_service
from app.input_context.normalization.query import QueryNormalizer
from app.input_context.retrieval.candidate import RetrievalCandidate
from app.input_context.retrieval.planning import RetrievalPlanner
from app.input_context.retrieval.policy import DEFAULT_RETRIEVAL_POLICY
from app.input_context.retrieval.ranking import RetrievalRanker
from app.input_context.retrieval.schemas import RetrievalQuery
from app.input_context.retrieval.snapshot import ProjectSnapshotReader
from app.input_context.retrieval.sources import RetrievalCandidateSource

ROOT = Path(__file__).resolve().parent
_ASCII = re.compile(r"[a-z0-9_.$#:/-]{2,}", re.IGNORECASE)
_CHINESE = re.compile(r"[\u3400-\u9fff]+")


def _candidate_text(candidate: RetrievalCandidate) -> str:
    values = [
        candidate.title,
        candidate.summary,
        candidate.logical_path or "",
        *candidate.high_fields,
        *candidate.medium_fields,
        *candidate.low_fields,
    ]
    return "\n".join(value for value in values if value)


def _features(text: str) -> Counter[str]:
    """生成确定性稀疏字符向量，避免引入正式运行时依赖。"""
    lowered = text.casefold()
    result: Counter[str] = Counter(_ASCII.findall(lowered))
    for sequence in _CHINESE.findall(lowered):
        for size in (1, 2, 3):
            for index in range(max(0, len(sequence) - size + 1)):
                result[f"zh{size}:{sequence[index : index + size]}"] += 1
    return result


def _idf_vectors(texts: list[str]) -> list[dict[str, float]]:
    counters = [_features(text) for text in texts]
    document_frequency: Counter[str] = Counter()
    for counter in counters:
        document_frequency.update(counter.keys())
    count = len(counters)
    vectors = []
    for counter in counters:
        vectors.append(
            {
                term: (1 + math.log(frequency))
                * (math.log((count + 1) / (document_frequency[term] + 1)) + 1)
                for term, frequency in counter.items()
            }
        )
    return vectors


def _cosine(left: dict[str, float], right: dict[str, float]) -> float:
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    if not left_norm or not right_norm:
        return 0.0
    shared = left.keys() & right.keys()
    return sum(left[key] * right[key] for key in shared) / (left_norm * right_norm)


def _vector_scores(
    candidates: list[RetrievalCandidate],
    query: str,
) -> list[float]:
    vectors = _idf_vectors([query, *[_candidate_text(item) for item in candidates]])
    return [_cosine(vectors[0], candidate) for candidate in vectors[1:]]


def _sort(candidates: list[RetrievalCandidate]) -> list[RetrievalCandidate]:
    return RetrievalRanker.sort([item for item in candidates if item.score > 0])


async def _rank(
    algorithm: str,
    candidates: list[RetrievalCandidate],
    query: str,
    plan,
    source: RetrievalCandidateSource,
    snapshot,
) -> list[RetrievalCandidate]:
    ranked = copy.deepcopy(candidates)
    ranker = RetrievalRanker()

    def assign() -> None:
        lexical = [ranker.score(item, plan) for item in ranked]
        vector = _vector_scores(ranked, query)
        lexical_max = max(lexical, default=0.0)
        for index, candidate in enumerate(ranked):
            lexical_normalized = (
                lexical[index] / lexical_max if lexical_max else 0.0
            )
            if algorithm == "lexical":
                candidate.score = lexical[index]
            elif algorithm == "vector":
                candidate.score = round(vector[index] * 100, 4)
            else:
                candidate.score = round(
                    (lexical_normalized * 0.65 + vector[index] * 0.35) * 100,
                    4,
                )

    assign()
    ranked = _sort(ranked)
    warnings: list[str] = []
    await source.hydrate_details(ranked, snapshot, plan, warnings)
    assign()
    return _sort(ranked)[: plan.result_limit]


def _metrics(
    ranked: list[RetrievalCandidate],
    relevant: Callable[[RetrievalCandidate], bool],
    relevant_total: int,
) -> dict[str, float | int]:
    top = ranked[:3]
    relevant_ranks = [index for index, item in enumerate(top, 1) if relevant(item)]
    recall = (
        len(relevant_ranks) / min(3, relevant_total) if relevant_total else 0.0
    )
    return {
        "recallAt3": round(recall, 4),
        "precisionAt3": round(len(relevant_ranks) / len(top), 4) if top else 0.0,
        "mrr": round(1 / relevant_ranks[0], 4) if relevant_ranks else 0.0,
        "relevantInTop3": len(relevant_ranks),
        "irrelevantInTop3": len(top) - len(relevant_ranks),
    }


def _hit(item: RetrievalCandidate) -> dict:
    return {
        "sourceType": item.source_type,
        "sourceId": item.source_id,
        "logicalPath": item.logical_path,
        "title": item.title,
        "summary": item.summary,
        "score": round(item.score, 4),
    }


def _latest_passed_baseline() -> Path:
    candidates = sorted(
        (ROOT / "output").glob("*/baseline-summary.json"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    for path in candidates:
        if json.loads(path.read_text(encoding="utf-8")).get("passed") is True:
            return path
    raise RuntimeError("没有找到已通过的七轮基准结果")


async def run(baseline_path: Path) -> dict:
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    user_id = int(baseline["userId"])
    project_id = int(baseline["projectId"])
    storage = get_object_storage()
    locations = StorageLocationFactory(get_settings().storage)
    reader = ProjectSnapshotReader(storage, locations)
    ranker = RetrievalRanker()
    source = RetrievalCandidateSource(reader, ranker)
    normalizer = QueryNormalizer(create_default_normalization_service())
    planner = RetrievalPlanner(DEFAULT_RETRIEVAL_POLICY)
    warnings: list[str] = []
    snapshot = await reader.load(user_id, project_id, warnings)
    if snapshot is None:
        raise RuntimeError("无法读取七轮基准生成的真实项目快照")

    cases: list[tuple[str, str, Callable[[RetrievalCandidate], bool]]] = [
        (
            "进度与下一阶段",
            "项目目前推进到什么程度，下一步的重点是什么？",
            lambda item: any(
                marker in _candidate_text(item)
                for marker in ("当前正在实现订单查询接口", "下一阶段目标", "next_stage_goal")
            ),
        ),
        (
            "安全约束",
            "项目对认证凭证泄露有哪些禁止要求？",
            lambda item: any(
                marker in _candidate_text(item)
                for marker in ("API Key", "访问令牌", "数据库密码", "凭据")
            ),
        ),
        (
            "代码实现定位",
            "订单列表查询现在落在哪个代码实现中？",
            lambda item: item.logical_path == "src/order_service.py",
        ),
    ]
    algorithms = ("lexical", "vector", "hybrid")
    rounds = []
    totals = {
        algorithm: {
            "recallAt3": 0.0,
            "precisionAt3": 0.0,
            "mrr": 0.0,
            "latencyMs": 0.0,
        }
        for algorithm in algorithms
    }
    for offset, (name, query, relevant) in enumerate(cases, 8):
        request = RetrievalQuery(query=query, limit=3)
        normalization = normalizer.normalize(query, project_id=project_id)
        plan = planner.build(request, normalization)
        base = await source.build(snapshot, plan, warnings)
        relevant_total = sum(relevant(item) for item in base)
        algorithms_result = {}
        for algorithm in algorithms:
            started_at = time.perf_counter()
            ranked = await _rank(
                algorithm,
                base,
                query,
                plan,
                source,
                snapshot,
            )
            latency_ms = round((time.perf_counter() - started_at) * 1000, 4)
            metrics = _metrics(ranked, relevant, relevant_total)
            algorithms_result[algorithm] = {
                "metrics": metrics,
                "latencyMs": latency_ms,
                "hits": [_hit(item) for item in ranked],
            }
            totals[algorithm]["recallAt3"] += float(metrics["recallAt3"])
            totals[algorithm]["precisionAt3"] += float(metrics["precisionAt3"])
            totals[algorithm]["mrr"] += float(metrics["mrr"])
            totals[algorithm]["latencyMs"] += latency_ms
        rounds.append(
            {
                "round": offset,
                "name": name,
                "query": query,
                "normalizedTerms": list(plan.normalized_terms),
                "candidateCount": len(base),
                "algorithms": algorithms_result,
            }
        )

    aggregate = {
        algorithm: {
            "meanRecallAt3": round(values["recallAt3"] / len(cases), 4),
            "meanPrecisionAt3": round(values["precisionAt3"] / len(cases), 4),
            "meanMrr": round(values["mrr"] / len(cases), 4),
            "meanLatencyMs": round(values["latencyMs"] / len(cases), 4),
        }
        for algorithm, values in totals.items()
    }
    lexical = aggregate["lexical"]
    alternatives = sorted(
        ("vector", "hybrid"),
        key=lambda name: (
            aggregate[name]["meanRecallAt3"],
            aggregate[name]["meanMrr"],
        ),
        reverse=True,
    )
    best = alternatives[0]
    improvement = (
        aggregate[best]["meanRecallAt3"] - lexical["meanRecallAt3"]
        + aggregate[best]["meanMrr"]
        - lexical["meanMrr"]
    )
    winner = best if improvement >= 0.05 else "lexical"
    return {
        "baseline": str(baseline_path),
        "userId": str(user_id),
        "projectId": str(project_id),
        "warnings": list(dict.fromkeys(warnings)),
        "rounds": rounds,
        "aggregate": aggregate,
        "winner": winner,
        "selectionReason": (
            "替代方案综合 Recall@3 与 MRR 有明确提升"
            if winner != "lexical"
            else "量化或混合方案未取得足够稳定的质量提升"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="执行三轮真实项目召回 A/B 测试")
    parser.add_argument("--baseline", type=Path)
    args = parser.parse_args()
    baseline = args.baseline or _latest_passed_baseline()
    result = asyncio.run(run(baseline))
    output = baseline.parent / "retrieval-ab-summary.json"
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    for item in result["rounds"]:
        print(f"第 {item['round']} 轮 {item['name']}：完成")
    print(f"召回对照完成，保留方案：{result['winner']}")
    print(f"结果：{output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

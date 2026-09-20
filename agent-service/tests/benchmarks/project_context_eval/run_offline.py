"""在冻结文件语料上执行 A0～A3 与首轮消融实验。"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import subprocess
import time
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

from app.core.config import get_settings
from app.llm.dependencies import get_structured_generator

from .dataset import dataset_sha256, load_dataset, resolve_annotation
from .fixture import ROOT, materialize, text_files
from .metrics import aggregate_query_runs, retrieval_metrics
from .models import RankedHit
from .rankers import BM25F, build_corpus, rank_a0, rank_a3, reciprocal_rank_fusion

ALGORITHMS = ("A0", "A1", "A2", "A3")
ABLATIONS = (
    "A0-no-query-normalization",
    "A0-no-phrase-bonus",
    "A0-no-field-weights",
    "A1-uniform-fields",
)


def _save_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def _safe_output(path: Path) -> Path:
    resolved = path.resolve()
    safe_root = (ROOT / "output").resolve()
    if not resolved.is_relative_to(safe_root):
        raise ValueError(f"结果目录必须位于 {safe_root} 内")
    return resolved


def _git_metadata() -> dict:
    repository = ROOT.parents[3]
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repository,
        text=True,
        capture_output=True,
        check=False,
    ).stdout.strip()
    status = subprocess.run(
        ["git", "status", "--short", "--untracked-files=all"],
        cwd=repository,
        text=True,
        capture_output=True,
        check=False,
    ).stdout.splitlines()
    return {
        "commit": commit,
        "dirty": bool(status),
        "statusSha256": hashlib.sha256("\n".join(status).encode()).hexdigest(),
        "changedPathCount": len(status),
    }


def _metric_payload(annotation, ranking) -> dict[str, float]:
    if not annotation.answerable:
        return {}
    relevance = {item.path: item.relevance for item in annotation.evidence}
    metrics = retrieval_metrics([item.path for item in ranking[:8]], relevance)
    metrics["path_accuracy@1"] = float(bool(ranking) and ranking[0].path in relevance)
    return metrics


def _record(question, algorithm: str, latency_ms: float, ranking, annotation, events=None, error=None) -> dict:
    return {
        "question_id": question.id,
        "algorithm": algorithm,
        "split": question.split,
        "category": question.category,
        "version": question.version,
        "latency_ms": round(latency_ms, 4),
        "hits": [
            RankedHit(
                rank=rank,
                path=item.path,
                score=item.score,
                explanation=item.explanation,
            ).model_dump(mode="json")
            for rank, item in enumerate(ranking[:10], 1)
        ],
        "metrics": _metric_payload(annotation, ranking),
        "model_events": events or [],
        "error": error,
    }


def _cost_summary(records: list[dict]) -> dict:
    model_events = [
        event
        for record in records
        for event in record.get("model_events", [])
        if event.get("type") == "model"
    ]
    usage = [
        event.get("response", {}).get("usage", {})
        for event in model_events
        if isinstance(event.get("response"), dict)
    ]
    return {
        "modelCalls": len(model_events),
        "promptTokens": sum(int(item.get("prompt_tokens", 0) or 0) for item in usage),
        "completionTokens": sum(int(item.get("completion_tokens", 0) or 0) for item in usage),
        "accountedCny": round(sum(float(item.get("accountedCny", 0) or 0) for item in model_events), 6),
        "usageKnownCalls": sum(bool(item.get("usageKnown")) for item in model_events),
    }


def _by_dimension(records: list[dict]) -> dict:
    result = {}
    for dimension in ("split", "category"):
        grouped: defaultdict[str, list[dict]] = defaultdict(list)
        for record in records:
            if record.get("metrics"):
                grouped[record[dimension]].append(record)
        result[dimension] = {
            key: aggregate_query_runs(items)
            for key, items in sorted(grouped.items())
        }
    return result


async def run(
    output: Path,
    selected: tuple[str, ...],
    with_ablations: bool,
    question_ids: frozenset[str] | None = None,
) -> dict:
    output = _safe_output(output)
    if output.exists() and any(output.iterdir()):
        raise ValueError(f"结果目录必须为空：{output}")
    output.mkdir(parents=True, exist_ok=True)
    questions, annotations = load_dataset()
    if question_ids:
        unknown = question_ids - {item.id for item in questions}
        if unknown:
            raise ValueError(f"指定了不存在的问题：{sorted(unknown)}")
        questions = [item for item in questions if item.id in question_ids]
    fixtures = {}
    corpora = {}
    resolved_annotations = {}
    for version in ("v1", "v2", "v3"):
        fixture = materialize(version, output / "fixtures" / version)
        files = text_files(fixture.root)
        fixtures[version] = fixture
        corpora[version] = build_corpus(files)
    for question in questions:
        files = text_files(fixtures[question.version].root)
        resolved_annotations[question.id] = resolve_annotation(
            annotations[question.id], files
        )

    started_at = datetime.now(UTC).isoformat()
    records: list[dict] = []
    record_path = output / "query-runs.jsonl"
    generator = get_structured_generator(1600) if "A3" in selected else None
    for index, question in enumerate(questions, 1):
        corpus = corpora[question.version]
        annotation = resolved_annotations[question.id]
        rankings = {}

        started = time.perf_counter()
        rankings["A0"] = rank_a0(question.question, corpus, limit=10)
        if "A0" in selected:
            records.append(_record(question, "A0", (time.perf_counter() - started) * 1000, rankings["A0"], annotation))

        started = time.perf_counter()
        rankings["A1"] = BM25F(corpus).rank(question.question, limit=10)
        if "A1" in selected:
            records.append(_record(question, "A1", (time.perf_counter() - started) * 1000, rankings["A1"], annotation))

        started = time.perf_counter()
        rankings["A2"] = reciprocal_rank_fusion([rankings["A0"], rankings["A1"]], limit=10)
        if "A2" in selected:
            records.append(_record(question, "A2", (time.perf_counter() - started) * 1000, rankings["A2"], annotation))

        if "A3" in selected:
            started = time.perf_counter()
            events: list[dict] = []
            try:
                ranking, events = await rank_a3(
                    question.question,
                    corpus,
                    rankings["A2"],
                    generator,
                    limit=10,
                    events=events,
                )
                records.append(_record(question, "A3", (time.perf_counter() - started) * 1000, ranking, annotation, events=events))
            except Exception as exception:  # noqa: BLE001
                failed_record = _record(
                        question,
                        "A3",
                        (time.perf_counter() - started) * 1000,
                        rankings["A2"],
                        annotation,
                        events=events,
                        error=f"{type(exception).__name__}: {exception}",
                    )
                failed_record["metrics"] = {}
                records.append(failed_record)

        if with_ablations:
            variants = {
                "A0-no-query-normalization": "no_query_normalization",
                "A0-no-phrase-bonus": "no_phrase_bonus",
                "A0-no-field-weights": "no_field_weights",
            }
            for name, variant in variants.items():
                started = time.perf_counter()
                ranking = rank_a0(
                    question.question,
                    corpus,
                    10,
                    variant=variant,
                )
                records.append(_record(question, name, (time.perf_counter() - started) * 1000, ranking, annotation))
            started = time.perf_counter()
            uniform_ranking = BM25F(
                corpus,
                field_weights={
                    "path": 1,
                    "title": 1,
                    "heading": 1,
                    "content": 1,
                },
            ).rank(question.question, 10)
            records.append(
                _record(
                    question,
                    "A1-uniform-fields",
                    (time.perf_counter() - started) * 1000,
                    uniform_ranking,
                    annotation,
                )
            )

        record_path.write_text(
            "\n".join(json.dumps(item, ensure_ascii=False) for item in records) + "\n",
            encoding="utf-8",
        )
        print(f"[{index:02d}/{len(questions):02d}] {question.id} 完成", flush=True)

    answerable_records = [item for item in records if item["metrics"]]
    aggregate = aggregate_query_runs(answerable_records)
    result = {
        "schemaVersion": "1.0",
        "startedAt": started_at,
        "finishedAt": datetime.now(UTC).isoformat(),
        "executionMode": "offline-materialized-corpus",
        "datasetSha256": dataset_sha256(),
        "algorithms": list(selected),
        "ablations": list(ABLATIONS) if with_ablations else [],
        "questionCount": len(questions),
        "answerableQuestionCount": sum(item.answerable for item in resolved_annotations.values()),
        "unanswerableQuestionCount": sum(not item.answerable for item in resolved_annotations.values()),
        "fixtureManifests": {key: value.manifest for key, value in fixtures.items()},
        "git": _git_metadata(),
        "aggregate": aggregate,
        "dimensions": _by_dimension(answerable_records),
        "modelUsage": _cost_summary(records),
        "passed": not any(item.get("error") for item in records),
        "limitations": [
            "A0 在物化文件全文上复用生产归一化与字段评分，但不等同于 MinIO 解析后候选。",
            "本阶段只评估文件级召回；无答案识别、引用正确率和回答忠实度由真实 Agent 回答阶段统计。",
            "A3 仅重排 A2 的前 10 个候选，无法召回前 10 之外的漏失证据。",
        ],
    }
    _save_json(output / "aggregate.json", result)
    _save_json(
        output / "resolved-annotations.json",
        {key: value.model_dump(mode="json") for key, value in resolved_annotations.items()},
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="执行冻结语料 A0～A3 评测")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--algorithms", nargs="+", choices=ALGORITHMS, default=list(ALGORITHMS))
    parser.add_argument("--with-ablations", action="store_true")
    parser.add_argument("--question-ids", nargs="+")
    args = parser.parse_args()
    selected = tuple(dict.fromkeys(args.algorithms))
    if (
        "A3" in selected
        and not get_settings().llm.get_llm_config("deepseek").api_key
    ):
        raise SystemExit("运行 A3 需要设置 DEEPSEEK_API_KEY")
    output = args.output.resolve()
    try:
        result = asyncio.run(
            run(
                output,
                selected,
                args.with_ablations,
                frozenset(args.question_ids) if args.question_ids else None,
            )
        )
    except Exception as exception:
        if output.is_relative_to((ROOT / "output").resolve()):
            _save_json(output / "failure.json", {"errorType": type(exception).__name__, "error": str(exception)})
        raise
    print(f"评测完成：{result['questionCount']} 题，结果位于 {output}")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

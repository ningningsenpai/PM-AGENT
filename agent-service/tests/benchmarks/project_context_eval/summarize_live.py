"""补采真实解析轨迹并汇总解析、回答的 Token、成本与延迟。"""

from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path
from uuid import uuid4

import httpx

from .dataset import dataset_sha256
from .fixture import ROOT


def _safe_live_output(path: Path) -> Path:
    resolved = path.resolve()
    root = (ROOT / "output").resolve()
    if not resolved.is_relative_to(root) or not resolved.is_dir():
        raise ValueError(f"真实结果目录必须位于 {root} 内且已经存在")
    return resolved


def _save_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return round(ordered[max(0, math.ceil(len(ordered) * percentile) - 1)], 3)


def _usage(events: list[dict]) -> dict:
    model_events = [event for event in events if event.get("type") == "model"]
    usages = [event.get("response", {}).get("usage", {}) for event in model_events if isinstance(event.get("response"), dict)]
    return {
        "modelCalls": len(model_events),
        "promptTokens": sum(int(item.get("prompt_tokens", 0) or 0) for item in usages),
        "completionTokens": sum(int(item.get("completion_tokens", 0) or 0) for item in usages),
        "totalTokens": sum(int(item.get("total_tokens", 0) or 0) for item in usages),
        "accountedCny": round(sum(float(item.get("accountedCny", 0) or 0) for item in model_events), 6),
        "usageKnownCalls": sum(bool(item.get("usageKnown")) for item in model_events),
    }


def _latency(values: list[float]) -> dict:
    return {
        "mean": round(statistics.fmean(values), 3) if values else 0.0,
        "p95": _percentile(values, 0.95),
    }


def run(live_output: Path) -> dict:
    live_output = _safe_live_output(live_output)
    state = json.loads((live_output / "local-resume.json").read_text(encoding="utf-8"))
    if state.get("datasetSha256") != dataset_sha256():
        raise ValueError("真实运行的数据集哈希与当前冻结集不一致")
    answers = [
        json.loads(line)
        for line in (live_output / "answers.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    headers = {"X-Trace-Id": f"project-eval-summary-{uuid4().hex}"}
    with httpx.Client(base_url=state["baseUrl"], timeout=180, trust_env=False) as client:
        login = client.post(
            "/api/v1/auth/login",
            headers=headers,
            json={"email": state["email"], "password": state["password"]},
        )
        login.raise_for_status()
        token = login.json()["data"]["tokenValue"]
        auth = {"Authorization": f"Bearer {token}", **headers}
        parse_traces = {}
        for version, version_state in state["versions"].items():
            run_id = version_state["parse"]["runId"]
            response = client.get(f"/api/v1/agent/runs/{run_id}", headers=auth)
            response.raise_for_status()
            body = response.json()
            if body.get("code") != 200:
                raise RuntimeError(f"{version} 解析轨迹读取失败：{body.get('message')}")
            parse_traces[version] = body["data"]

    _save_json(live_output / "parse-traces.json", parse_traces)
    parse_events = [event for trace in parse_traces.values() for event in trace.get("events", [])]
    answer_events = [
        event
        for answer in answers
        for event in (answer.get("result") or {}).get("events", [])
    ]
    request_records = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in (live_output / "requests").glob("*.json")
    ]
    parse_latencies = [
        float(item["elapsedMs"])
        for item in request_records
        if str(item.get("label", "")).startswith("parse-v")
    ]
    answer_latencies = [float(item["latencyMs"]) for item in answers]
    parse_results = {version: item["parse"] for version, item in state["versions"].items()}
    summary = {
        "schemaVersion": "1.0",
        "datasetSha256": dataset_sha256(),
        "completed": bool(state.get("completed")),
        "versions": {
            version: {
                "projectId": version_state["projectId"],
                "snapshotSha256": version_state["fixtureManifest"]["snapshotSha256"],
                "uploadedCount": len(version_state["uploaded"]),
                "skippedCount": len(version_state["skipped"]),
                "parse": version_state["parse"],
                "answerCount": sum(item["version"] == version for item in answers),
            }
            for version, version_state in state["versions"].items()
        },
        "parse": {
            "candidateCount": sum(item["candidateCount"] for item in parse_results.values()),
            "successCount": sum(item["successCount"] for item in parse_results.values()),
            "failureCount": sum(item["failureCount"] for item in parse_results.values()),
            "latencyMs": _latency(parse_latencies),
            "modelUsage": _usage(parse_events),
        },
        "answers": {
            "count": len(answers),
            "successCount": sum((item.get("result") or {}).get("status") == "success" for item in answers),
            "latencyMs": _latency(answer_latencies),
            "modelUsage": _usage(answer_events),
        },
        "totalModelUsage": _usage(parse_events + answer_events),
    }
    summary["passed"] = (
        summary["completed"]
        and summary["parse"]["failureCount"] == 0
        and summary["answers"]["count"] == 50
        and summary["answers"]["successCount"] == 50
    )
    _save_json(live_output / "live-aggregate.json", summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="汇总真实解析与问答运行")
    parser.add_argument("--live-output", type=Path, required=True)
    args = parser.parse_args()
    summary = run(args.live_output)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

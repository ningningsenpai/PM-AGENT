"""对真实 Agent 回答执行冻结标注评分与结构化忠实度评审。"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import statistics
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Literal

from pydantic import Field, model_validator

from app.core.config import get_settings
from app.llm.dependencies import get_structured_generator
from app.llm.telemetry import capture_calls
from app.project_context.file_detail.sensitive_content import sanitize_sensitive_content

from .dataset import dataset_sha256, load_dataset
from .fixture import ROOT, materialize, text_files
from .models import Annotation, StrictModel


class PointAssessment(StrictModel):
    point: str
    present: bool
    reason: str = Field(min_length=1, max_length=240)


class CitationAssessment(StrictModel):
    path: str
    supported: bool
    reason: str = Field(min_length=1, max_length=240)


class AnswerJudgeOutput(StrictModel):
    disposition: Literal["answered", "insufficient", "corrected"]
    answerability_prediction: Literal["answerable", "unanswerable"]
    required_points: list[PointAssessment]
    forbidden_points: list[PointAssessment]
    correction_satisfied: bool | None
    factual_claim_count: int = Field(ge=0, le=100)
    unsupported_claim_count: int = Field(ge=0, le=100)
    citations: list[CitationAssessment]
    explanation: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def validate_claim_counts(self) -> AnswerJudgeOutput:
        if self.unsupported_claim_count > self.factual_claim_count:
            raise ValueError("无依据事实数不得超过事实声明总数")
        return self


def _save_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def _safe_directory(path: Path, *, must_exist: bool) -> Path:
    resolved = path.resolve()
    root = (ROOT / "output").resolve()
    if not resolved.is_relative_to(root):
        raise ValueError(f"目录必须位于 {root} 内")
    if must_exist and not resolved.is_dir():
        raise ValueError(f"目录不存在：{resolved}")
    return resolved


def _load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _answer_text(record: dict) -> str:
    result = record.get("result") or {}
    nested = result.get("result") or {}
    answer = nested.get("answer") or result.get("answer")
    if not isinstance(answer, str) or not answer.strip():
        raise ValueError(f"{record.get('questionId')} 缺少回答正文")
    return answer.strip()


def extract_citation_paths(answer: str, paths: list[str]) -> list[str]:
    """识别完整逻辑路径，以及语料中唯一的文件名引用。"""
    found = {path for path in paths if path in answer}
    basenames: dict[str, list[str]] = {}
    for path in paths:
        basenames.setdefault(PurePosixPath(path).name, []).append(path)
    for basename, matching_paths in basenames.items():
        if len(matching_paths) == 1 and basename in answer:
            found.add(matching_paths[0])
    return sorted(found)


def _reference_blocks(
    annotation: Annotation,
    files: dict[str, str],
    citations: list[str],
) -> str:
    blocks = []
    cited = set(citations)
    for evidence in annotation.evidence:
        anchors = "\n".join(f"- {anchor}" for anchor in evidence.anchors)
        blocks.append(f"人工证据路径：{evidence.path}\n人工证据片段：\n{anchors}")
        cited.discard(evidence.path)
    for path in sorted(cited):
        sanitized = sanitize_sensitive_content(files[path][:8000]).text
        blocks.append(f"回答引用路径：{path}\n文件内容：\n{sanitized}")
    return "\n\n---\n\n".join(blocks) or "无可支持该问题具体答案的人工证据。"


def _judge_prompt(
    question: str,
    annotation: Annotation,
    answer: str,
    citations: list[str],
    references: str,
) -> str:
    required = json.dumps(annotation.required_points, ensure_ascii=False)
    forbidden = json.dumps(annotation.forbidden_points, ensure_ascii=False)
    correction = json.dumps(annotation.expected_correction, ensure_ascii=False)
    cited = json.dumps(citations, ensure_ascii=False)
    return f"""你是项目问答评测员，只评分，不改写答案。

判定规则：
1. disposition=answered：回答尝试给出具体项目事实；insufficient：明确说明资料不足且没有臆造具体答案；corrected：明确否定问题中的错误前提并给出正确状态。
2. answerability_prediction 只描述回答自身的结论：能依据项目资料给出所问事实或可核实纠正时为 answerable；明确认为资料没有答案、对象不存在、无法得出或拒绝臆测时为 unanswerable。不要根据必答点列表猜测标签。
3. required_points 对下面每个必答点原样返回一次，present 表示回答是否覆盖其语义。
4. forbidden_points 对下面每个禁答点原样返回一次，present 表示回答是否错误声称了该内容。
5. correction_satisfied：存在预期纠正时判断是否完成，否则必须为 null。
6. factual_claim_count 统计可由项目资料核验的事实声明；unsupported_claim_count 统计参考证据无法支持、互相冲突或被夸大的事实声明。
7. citations 对给定引用路径原样返回一次；supported 只有在回答把该路径关联到的具体说法能被该文件内容直接支持时才为 true。没有引用则返回空数组。
8. 只把下方参考证据当作项目事实来源。不要用常识补全。

问题：{question}
必答点：{required}
禁答点：{forbidden}
预期纠正：{correction}
识别出的引用路径：{cited}

参考证据：
{references}

待评分回答：
{sanitize_sensitive_content(answer).text}

必须严格满足 JSON Schema：{AnswerJudgeOutput.model_json_schema()}"""


def _validate_labels(
    output: AnswerJudgeOutput,
    annotation: Annotation,
    citations: list[str],
) -> None:
    checks = (
        ("必答点", [item.point for item in output.required_points], annotation.required_points),
        ("禁答点", [item.point for item in output.forbidden_points], annotation.forbidden_points),
        ("引用", [item.path for item in output.citations], citations),
    )
    for label, actual, expected in checks:
        if len(actual) != len(set(actual)) or set(actual) != set(expected):
            raise ValueError(f"{label}评分项与输入不一致：actual={actual} expected={expected}")
    if annotation.expected_correction is None and output.correction_satisfied is not None:
        raise ValueError("无预期纠正的问题必须返回 correction_satisfied=null")
    if annotation.expected_correction is not None and output.correction_satisfied is None:
        raise ValueError("有预期纠正的问题必须返回 correction_satisfied 布尔值")


def _model_usage(records: list[dict]) -> dict:
    events = [event for record in records for event in record.get("judgeEvents", []) if event.get("type") == "model"]
    usages = [event.get("response", {}).get("usage", {}) for event in events if isinstance(event.get("response"), dict)]
    return {
        "modelCalls": len(events),
        "promptTokens": sum(int(item.get("prompt_tokens", 0) or 0) for item in usages),
        "completionTokens": sum(int(item.get("completion_tokens", 0) or 0) for item in usages),
        "accountedCny": round(sum(float(item.get("accountedCny", 0) or 0) for item in events), 6),
        "usageKnownCalls": sum(bool(item.get("usageKnown")) for item in events),
    }


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, math.ceil(percentile * len(ordered)) - 1)
    return round(ordered[index], 4)


def _aggregate(records: list[dict], annotations: dict[str, Annotation]) -> dict:
    successful = [item for item in records if not item.get("error")]
    required_total = sum(len(annotations[item["questionId"]].required_points) for item in records)
    required_hits = sum(sum(check["present"] for check in item["judge"]["required_points"]) for item in successful)
    forbidden_total = sum(len(annotations[item["questionId"]].forbidden_points) for item in records)
    forbidden_hits = sum(sum(check["present"] for check in item["judge"]["forbidden_points"]) for item in successful)

    predicted_unanswerable = {
        item["questionId"]
        for item in successful
        if item["judge"]["answerability_prediction"] == "unanswerable"
    }
    gold_unanswerable = {question_id for question_id, item in annotations.items() if not item.answerable}
    true_positive = len(predicted_unanswerable & gold_unanswerable)
    precision = true_positive / len(predicted_unanswerable) if predicted_unanswerable else 0.0
    recall = true_positive / len(gold_unanswerable) if gold_unanswerable else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0

    citations = [citation for item in successful for citation in item["judge"]["citations"]]
    supported_citations = sum(item["supported"] for item in citations)
    relevant_citations = 0
    covered_answerable = 0
    for item in successful:
        annotation = annotations[item["questionId"]]
        evidence_paths = {evidence.path for evidence in annotation.evidence}
        item_citations = item["judge"]["citations"]
        relevant_citations += sum(citation["supported"] and citation["path"] in evidence_paths for citation in item_citations)
        if annotation.answerable and any(citation["supported"] for citation in item_citations):
            covered_answerable += 1

    claim_count = sum(item["judge"]["factual_claim_count"] for item in successful)
    unsupported_count = sum(item["judge"]["unsupported_claim_count"] for item in successful)
    correction_records = [item for item in records if annotations[item["questionId"]].expected_correction is not None]
    successful_corrections = {
        item["questionId"]: bool(item["judge"]["correction_satisfied"])
        for item in successful
        if annotations[item["questionId"]].expected_correction is not None
    }
    answerable_count = sum(annotations[item["questionId"]].answerable for item in records)
    latencies = [float(item["latencyMs"]) for item in records]
    return {
        "scoredAnswers": len(successful),
        "unscoredAnswers": len(records) - len(successful),
        "requiredPointCoverage": round(required_hits / required_total, 6) if required_total else 1.0,
        "forbiddenPointViolationRate": round(forbidden_hits / forbidden_total, 6) if forbidden_total else 0.0,
        "noAnswerPrecision": round(precision, 6),
        "noAnswerRecall": round(recall, 6),
        "noAnswerF1": round(f1, 6),
        "falsePremiseCorrectionRate": round(
            sum(successful_corrections.get(item["questionId"], False) for item in correction_records) / len(correction_records),
            6,
        ) if correction_records else 1.0,
        "citationCount": len(citations),
        "citationCorrectness": round(supported_citations / len(citations), 6) if citations else 0.0,
        "citationGoldRelevance": round(relevant_citations / len(citations), 6) if citations else 0.0,
        "citationCoverage": round(covered_answerable / answerable_count, 6) if answerable_count else 0.0,
        "faithfulness": round(1 - unsupported_count / claim_count, 6) if claim_count else 1.0,
        "factualClaimCount": claim_count,
        "unsupportedClaimCount": unsupported_count,
        "answerLatencyMs": {
            "mean": round(statistics.fmean(latencies), 4) if latencies else 0.0,
            "p95": _percentile(latencies, 0.95),
        },
    }


async def run(live_output: Path, output: Path) -> dict:
    live_output = _safe_directory(live_output, must_exist=True)
    output = _safe_directory(output, must_exist=False)
    if output.exists() and any(output.iterdir()):
        raise ValueError(f"结果目录必须为空：{output}")
    output.mkdir(parents=True, exist_ok=True)

    questions, annotations = load_dataset()
    question_map = {item.id: item for item in questions}
    answers = _load_jsonl(live_output / "answers.jsonl")
    if len(answers) != len(questions) or {item["questionId"] for item in answers} != set(question_map):
        raise ValueError("真实回答必须与 50 道冻结问题一一对应")

    corpora = {}
    manifests = {}
    for version in ("v1", "v2", "v3"):
        fixture = materialize(version, output / "fixtures" / version)
        corpora[version] = text_files(fixture.root)
        manifests[version] = fixture.manifest

    generator = get_structured_generator(3000)
    records = []
    record_path = output / "answer-judgments.jsonl"
    started_at = datetime.now(UTC).isoformat()
    for index, answer_record in enumerate(answers, 1):
        question_id = answer_record["questionId"]
        question = question_map[question_id]
        annotation = annotations[question_id]
        files = corpora[question.version]
        citations: list[str] = []
        events: list[dict] = []
        record = {
            "questionId": question_id,
            "version": question.version,
            "split": question.split,
            "category": question.category,
            "latencyMs": answer_record["latencyMs"],
            "citationsDetected": citations,
            "judge": None,
            "judgeEvents": events,
            "error": None,
        }
        try:
            run_result = answer_record.get("result") or {}
            if run_result.get("status") != "success":
                raise ValueError(
                    f"Agent 运行失败：{run_result.get('error') or run_result.get('status')}"
                )
            answer = _answer_text(answer_record)
            citations = extract_citation_paths(answer, list(files))
            record["citationsDetected"] = citations
            prompt = _judge_prompt(
                question.question,
                annotation,
                answer,
                citations,
                _reference_blocks(annotation, files, citations),
            )
            with capture_calls(events):
                judged = await generator.generate(prompt, AnswerJudgeOutput)
            _validate_labels(judged, annotation, citations)
            record["judge"] = judged.model_dump(mode="json")
        except Exception as exception:  # noqa: BLE001
            record["error"] = f"{type(exception).__name__}: {exception}"
        records.append(record)
        record_path.write_text(
            "\n".join(json.dumps(item, ensure_ascii=False) for item in records) + "\n",
            encoding="utf-8",
        )
        print(f"[{index:02d}/{len(answers):02d}] {question_id} 评分完成", flush=True)

    aggregate = {
        "schemaVersion": "1.0",
        "startedAt": started_at,
        "finishedAt": datetime.now(UTC).isoformat(),
        "datasetSha256": dataset_sha256(),
        "liveOutput": live_output.name,
        "questionCount": len(questions),
        "fixtureManifests": manifests,
        "metrics": _aggregate(records, annotations),
        "judgeModelUsage": _model_usage(records),
        "passed": not any(item["error"] for item in records),
        "limitations": [
            "必答点、禁答点、错误前提和忠实度由冻结规则结合独立结构化裁判评分。",
            "引用路径先按完整逻辑路径或唯一文件名确定性解析，再由裁判检查对应说法是否受文件支持。",
            "忠实度仅以人工证据和回答明确引用文件为事实边界；未引用且不在人工证据中的扩展事实会被视为无依据。",
        ],
    }
    _save_json(output / "aggregate.json", aggregate)
    return aggregate


def main() -> int:
    parser = argparse.ArgumentParser(description="评估真实 Agent 回答质量")
    parser.add_argument("--live-output", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--allow-external-model-data", action="store_true")
    args = parser.parse_args()
    if not args.allow_external_model_data:
        raise SystemExit("回答评分会发送已脱敏回答和证据到外部模型，必须显式确认")
    if not get_settings().llm.get_llm_config("deepseek").api_key:
        raise SystemExit("回答评分需要设置 DEEPSEEK_API_KEY")
    result = asyncio.run(run(args.live_output, args.output))
    print(f"回答评分完成：{result['questionCount']} 题，结果位于 {args.output.resolve()}")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

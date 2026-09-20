"""冻结问题集加载、锚点解析和完整性校验。"""

from __future__ import annotations

import hashlib
from collections import Counter
from pathlib import Path

from .fixture import ROOT
from .models import Annotation, Question, ResolvedAnnotation, ResolvedEvidence

DATASET_ROOT = ROOT / "dataset"
QUESTIONS_PATH = DATASET_ROOT / "questions.jsonl"
ANNOTATIONS_PATH = DATASET_ROOT / "annotations.jsonl"

EXPECTED_CATEGORIES = {
    "direct": 8,
    "paraphrase": 8,
    "cross_file": 10,
    "false_premise": 6,
    "unanswerable": 6,
    "history": 6,
    "code_location": 6,
}


def _read_jsonl(path: Path, model_type):
    records = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            records.append(model_type.model_validate_json(line))
        except Exception as exception:
            raise ValueError(f"{path.name} 第 {line_number} 行不合法：{exception}") from exception
    return records


def load_dataset() -> tuple[list[Question], dict[str, Annotation]]:
    questions = _read_jsonl(QUESTIONS_PATH, Question)
    annotations = _read_jsonl(ANNOTATIONS_PATH, Annotation)
    annotation_map = {item.question_id: item for item in annotations}
    if len(annotation_map) != len(annotations):
        raise ValueError("人工标注中存在重复 question_id")
    question_ids = [item.id for item in questions]
    if len(set(question_ids)) != len(question_ids):
        raise ValueError("问题集中存在重复 id")
    if set(question_ids) != set(annotation_map):
        missing = sorted(set(question_ids) - set(annotation_map))
        extra = sorted(set(annotation_map) - set(question_ids))
        raise ValueError(f"问题与标注不一一对应：missing={missing} extra={extra}")
    split_counts = Counter(item.split for item in questions)
    if split_counts != {"dev": 35, "holdout": 15}:
        raise ValueError(f"数据划分必须是 35/15，当前为 {dict(split_counts)}")
    category_counts = Counter(item.category for item in questions)
    if category_counts != EXPECTED_CATEGORIES:
        raise ValueError(f"问题类型数量不符合冻结设计：{dict(category_counts)}")
    return questions, annotation_map


def _line_range(content: str, anchor: str) -> tuple[int, int]:
    if content.count(anchor) != 1:
        raise ValueError(f"证据锚点必须在文件中恰好出现一次：{anchor!r}")
    offset = content.index(anchor)
    start = content.count("\n", 0, offset) + 1
    end = start + anchor.count("\n")
    return start, end


def resolve_annotation(
    annotation: Annotation,
    files: dict[str, str],
) -> ResolvedAnnotation:
    evidence: list[ResolvedEvidence] = []
    for label in annotation.evidence:
        if label.path not in files:
            raise ValueError(f"{annotation.question_id} 的证据文件不存在：{label.path}")
        content = files[label.path]
        evidence.append(
            ResolvedEvidence(
                path=label.path,
                relevance=label.relevance,
                anchors=label.anchors,
                line_ranges=[_line_range(content, anchor) for anchor in label.anchors],
                content_sha256=hashlib.sha256(content.encode()).hexdigest(),
            )
        )
    return ResolvedAnnotation(
        question_id=annotation.question_id,
        answerable=annotation.answerable,
        evidence=evidence,
        required_points=annotation.required_points,
        forbidden_points=annotation.forbidden_points,
        expected_correction=annotation.expected_correction,
    )


def dataset_sha256() -> str:
    payload = QUESTIONS_PATH.read_bytes() + b"\n" + ANNOTATIONS_PATH.read_bytes()
    return hashlib.sha256(payload).hexdigest()

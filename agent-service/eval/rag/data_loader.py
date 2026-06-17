"""RAG 测试数据加载与评估。"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from config import GOLD_ANSWERS_FILE, QUESTIONS_FILE, RAW_DIALOGUES_FILE


@dataclass(frozen=True)
class RawDialogue:
    raw_id: str
    global_index: int
    project_id: str
    project_name: str
    turn_no: int
    module: str
    memory_text: str
    status: str


@dataclass(frozen=True)
class QuestionItem:
    question_id: str
    global_index: int
    project_id: str
    project_name: str
    question_no: int
    question_type: str
    question_text: str


@dataclass(frozen=True)
class GoldAnswer:
    answer_id: str
    question_id: str
    project_id: str
    expected_raw_ids: list[str]
    must_hit_raw_ids: list[str]
    support_raw_ids: list[str]
    superseded_raw_ids: list[str]
    expected_answer_points: str
    expected_behavior: str


def _load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def load_raw_dialogues() -> list[RawDialogue]:
    rows = _load_csv(RAW_DIALOGUES_FILE)
    return [
        RawDialogue(
            raw_id=row["raw_id"],
            global_index=int(row["global_index"]),
            project_id=row["project_id"],
            project_name=row["project_name"],
            turn_no=int(row["turn_no"]),
            module=row["module"],
            memory_text=row["memory_text"],
            status=row["status"],
        )
        for row in rows
    ]


def load_questions() -> list[QuestionItem]:
    rows = _load_csv(QUESTIONS_FILE)
    return [
        QuestionItem(
            question_id=row["question_id"],
            global_index=int(row["global_index"]),
            project_id=row["project_id"],
            project_name=row["project_name"],
            question_no=int(row["question_no"]),
            question_type=row["question_type"],
            question_text=row["question_text"],
        )
        for row in rows
    ]


def load_gold_answers() -> dict[str, GoldAnswer]:
    rows = _load_csv(GOLD_ANSWERS_FILE)
    answers: dict[str, GoldAnswer] = {}
    for row in rows:
        answers[row["question_id"]] = GoldAnswer(
            answer_id=row["answer_id"],
            question_id=row["question_id"],
            project_id=row["project_id"],
            expected_raw_ids=json.loads(row["expected_raw_ids"]),
            must_hit_raw_ids=json.loads(row["must_hit_raw_ids"]),
            support_raw_ids=json.loads(row["support_raw_ids"]),
            superseded_raw_ids=json.loads(row["superseded_raw_ids"]),
            expected_answer_points=row["expected_answer_points"],
            expected_behavior=row["expected_behavior"],
        )
    return answers


def load_all() -> tuple[list[RawDialogue], list[QuestionItem], dict[str, GoldAnswer]]:
    return load_raw_dialogues(), load_questions(), load_gold_answers()

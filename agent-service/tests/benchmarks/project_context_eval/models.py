"""评测数据、标注与运行结果的严格数据模型。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

QuestionCategory = Literal[
    "direct",
    "paraphrase",
    "cross_file",
    "false_premise",
    "unanswerable",
    "history",
    "code_location",
]
DatasetSplit = Literal["dev", "holdout"]
FixtureVersion = Literal["v1", "v2", "v3"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Question(StrictModel):
    id: str = Field(pattern=r"^[DSXFNH C][0-9]{3}$".replace(" ", ""))
    split: DatasetSplit
    category: QuestionCategory
    version: FixtureVersion
    question: str = Field(min_length=4, max_length=500)
    tags: list[str] = Field(default_factory=list, max_length=12)


class EvidenceLabel(StrictModel):
    path: str = Field(min_length=1)
    relevance: int = Field(default=1, ge=1, le=3)
    anchors: list[str] = Field(default_factory=list, min_length=1, max_length=5)


class Annotation(StrictModel):
    question_id: str
    answerable: bool
    evidence: list[EvidenceLabel] = Field(default_factory=list, max_length=12)
    required_points: list[str] = Field(default_factory=list, max_length=12)
    forbidden_points: list[str] = Field(default_factory=list, max_length=12)
    expected_correction: str | None = None

    @model_validator(mode="after")
    def validate_answerability(self) -> Annotation:
        if self.answerable and not self.evidence:
            raise ValueError("可回答问题必须至少标注一条证据")
        if not self.answerable and self.evidence:
            raise ValueError("无答案问题不得标注证据")
        if not self.answerable and not self.forbidden_points:
            raise ValueError("无答案问题必须标注不得臆测的内容")
        return self


class ResolvedEvidence(StrictModel):
    path: str
    relevance: int
    anchors: list[str]
    line_ranges: list[tuple[int, int]]
    content_sha256: str


class ResolvedAnnotation(StrictModel):
    question_id: str
    answerable: bool
    evidence: list[ResolvedEvidence]
    required_points: list[str]
    forbidden_points: list[str]
    expected_correction: str | None


class RankedHit(StrictModel):
    rank: int = Field(ge=1)
    path: str
    score: float
    explanation: dict[str, float | int | str] = Field(default_factory=dict)


class QueryRun(StrictModel):
    question_id: str
    algorithm: str
    split: DatasetSplit
    category: QuestionCategory
    version: FixtureVersion
    latency_ms: float = Field(ge=0)
    hits: list[RankedHit]
    metrics: dict[str, float]
    model_events: list[dict] = Field(default_factory=list)
    error: str | None = None

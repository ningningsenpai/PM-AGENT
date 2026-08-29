"""可解释词法排序测试。"""

from __future__ import annotations

from app.input_context.retrieval.candidate import RetrievalCandidate
from app.input_context.retrieval.planning import RetrievalPlan, WeightedTerm
from app.input_context.retrieval.ranking import RetrievalRanker


def _plan() -> RetrievalPlan:
    return RetrievalPlan(
        raw_query="SQL 注入",
        cleaned_query="sql 注入",
        terms=(
            WeightedTerm("sql 注入", "canonical", 1.5),
            WeightedTerm("sql", "technical", 1.25),
        ),
        allowed_source_types=frozenset({"file_detail"}),
        evidence_level="summary",
        candidate_limit=8,
        result_limit=5,
    )


def test_score_breakdown_matches_total_score() -> None:
    candidate = RetrievalCandidate(
        source_type="file_detail",
        source_id="file-1",
        title="仓储实现",
        summary="存在 SQL 注入风险",
        high_fields=["StudentRepository SQL 注入"],
        medium_fields=["拼接 SQL"],
        importance="high",
    )

    score = RetrievalRanker().score(candidate, _plan())

    assert candidate.score_breakdown is not None
    assert score == candidate.score_breakdown.total
    assert candidate.score_breakdown.high_fields > 0
    assert candidate.score_breakdown.term_source_weight > 0
    assert candidate.score_breakdown.importance == 1.0


def test_equal_scores_use_source_priority_then_stable_source_id() -> None:
    candidates = [
        RetrievalCandidate("project_specification", "b", "b", "b", score=1),
        RetrievalCandidate("file_detail", "c", "c", "c", score=1),
        RetrievalCandidate("file_detail", "a", "a", "a", score=1),
    ]

    ranked = RetrievalRanker.sort(candidates)

    assert [item.source_id for item in ranked] == ["a", "c", "b"]

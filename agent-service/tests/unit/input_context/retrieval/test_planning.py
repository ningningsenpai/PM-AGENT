"""带权召回计划测试。"""

from __future__ import annotations

from app.input_context.normalization.query import QueryNormalization
from app.input_context.retrieval.planning import RetrievalPlanner
from app.input_context.retrieval.policy import DEFAULT_RETRIEVAL_POLICY
from app.input_context.retrieval.schemas import RetrievalQuery


def _normalization(
    raw_text: str,
    cleaned_text: str | None = None,
    normalized_terms: tuple[str, ...] = (),
) -> QueryNormalization:
    result = type(
        "NormalizationFixture",
        (),
        {"normalized_terms": normalized_terms},
    )()
    return QueryNormalization(
        raw_text=raw_text,
        cleaned_text=cleaned_text or raw_text.casefold(),
        result=result,
    )


def test_plan_keeps_term_source_and_uses_highest_duplicate_weight() -> None:
    plan = RetrievalPlanner(DEFAULT_RETRIEVAL_POLICY).build(
        RetrievalQuery(query="API 风险"),
        _normalization("API 风险", normalized_terms=("API", "项目风险")),
    )

    api_term = next(term for term in plan.terms if term.text == "api")
    assert api_term.source == "canonical"
    assert api_term.weight == 1.5
    assert any(term.source == "chinese_fallback" for term in plan.terms)


def test_plan_extracts_technical_identifier_and_removes_exact_stop_terms() -> None:
    plan = RetrievalPlanner(DEFAULT_RETRIEVAL_POLICY).build(
        RetrievalQuery(query="这个项目如何调用 Foo_Bar"),
        _normalization("这个项目如何调用 Foo_Bar"),
    )

    terms = {term.text: term for term in plan.terms}
    assert terms["foo_bar"].source == "technical"
    assert terms["foo_bar"].weight == 1.25
    assert not {"这个", "项目", "如何"}.intersection(terms)


def test_summary_evidence_disables_raw_source_even_for_code_question() -> None:
    plan = RetrievalPlanner(DEFAULT_RETRIEVAL_POLICY).build(
        RetrievalQuery(query="给出代码证据", evidence_level="summary"),
        _normalization("给出代码证据"),
    )

    assert not plan.read_source


def test_auto_evidence_enables_raw_source_for_exact_code_question() -> None:
    plan = RetrievalPlanner(DEFAULT_RETRIEVAL_POLICY).build(
        RetrievalQuery(query="给出代码证据"),
        _normalization("给出代码证据"),
    )

    assert plan.read_source


def test_auto_focus_only_adds_habits_and_changes_when_intent_matches() -> None:
    planner = RetrievalPlanner(DEFAULT_RETRIEVAL_POLICY)
    ordinary = planner.build(
        RetrievalQuery(query="项目风险"),
        _normalization("项目风险"),
    )
    special = planner.build(
        RetrievalQuery(query="我的偏好和最近更新"),
        _normalization("我的偏好和最近更新"),
    )

    assert "user_habit" not in ordinary.allowed_source_types
    assert "update_journal" not in ordinary.allowed_source_types
    assert "user_habit" in special.allowed_source_types
    assert "update_journal" in special.allowed_source_types


def test_detail_candidate_budget_is_twice_limit_with_fixed_bounds() -> None:
    planner = RetrievalPlanner(DEFAULT_RETRIEVAL_POLICY)
    small = planner.build(
        RetrievalQuery(query="项目风险", limit=2),
        _normalization("项目风险"),
    )
    large = planner.build(
        RetrievalQuery(query="项目风险", limit=8),
        _normalization("项目风险"),
    )

    assert small.candidate_limit == 8
    assert large.candidate_limit == 16

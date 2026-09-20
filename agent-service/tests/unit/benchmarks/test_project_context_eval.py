"""单项目上下文评测的确定性单元测试。"""

from tests.benchmarks.project_context_eval.dataset import load_dataset
from tests.benchmarks.project_context_eval.evaluate_answers import (
    extract_citation_paths,
)
from tests.benchmarks.project_context_eval.metrics import retrieval_metrics
from tests.benchmarks.project_context_eval.rankers import (
    RankedDocument,
    reciprocal_rank_fusion,
)


def test_frozen_dataset_has_expected_shape() -> None:
    questions, annotations = load_dataset()

    assert len(questions) == 50
    assert len(annotations) == 50
    assert sum(item.split == "dev" for item in questions) == 35
    assert sum(item.split == "holdout" for item in questions) == 15


def test_retrieval_metrics_respect_graded_relevance() -> None:
    result = retrieval_metrics(
        ["docs/b.md", "docs/a.md", "docs/c.md"],
        {"docs/a.md": 3, "docs/c.md": 1},
    )

    assert result["recall@1"] == 0.0
    assert result["recall@3"] == 1.0
    assert result["mrr"] == 0.5
    assert 0 < result["ndcg@5"] < 1


def test_rrf_rewards_agreement_and_keeps_deterministic_order() -> None:
    first = [
        RankedDocument(path="a", score=10, explanation={}),
        RankedDocument(path="b", score=9, explanation={}),
    ]
    second = [
        RankedDocument(path="a", score=7, explanation={}),
        RankedDocument(path="c", score=6, explanation={}),
    ]

    result = reciprocal_rank_fusion([first, second])

    assert [item.path for item in result] == ["a", "b", "c"]
    assert result[0].score > result[1].score


def test_citation_extraction_supports_full_path_and_unique_basename() -> None:
    paths = [
        "backend/src/StudentRepository.java",
        "docs/开发文档.md",
        "archive/开发文档.md",
    ]

    result = extract_citation_paths(
        "见 `StudentRepository.java` 与 `docs/开发文档.md`。",
        paths,
    )

    assert result == ["backend/src/StudentRepository.java", "docs/开发文档.md"]

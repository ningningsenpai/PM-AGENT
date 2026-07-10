"""术语库发布前结构、冲突和效果检查。"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from app.normalization.lexicon.json_provider import DEFAULT_LEXICON_ROOT, JsonLexiconProvider
from app.normalization.lexicon.merger import LexiconMerger
from app.normalization.lexicon.validator import LexiconValidator
from app.normalization.mapping import SynonymMapper
from app.normalization.matching import AhoMatcher, LongestMatchResolver
from app.normalization.pipeline import NormalizationPipeline
from app.normalization.preprocessing import TextNormalizer
from eval.normalization.evaluate import DEFAULT_CASES_PATH, evaluate_all, load_cases

__all__ = ["run_release_check"]


def run_release_check(
    *,
    lexicon_root: Path = DEFAULT_LEXICON_ROOT,
    cases_path: Path = DEFAULT_CASES_PATH,
    domain: str = "project_management",
    project_id: str | None = None,
    minimum_precision: float = 0.95,
    minimum_recall: float = 0.90,
    minimum_f1: float = 0.92,
) -> dict[str, Any]:
    """构建候选自动机并返回是否满足发布条件。"""
    text_normalizer = TextNormalizer()
    provider = JsonLexiconProvider(lexicon_root)
    validator = LexiconValidator(text_normalizer)
    merger = LexiconMerger(text_normalizer)
    matcher = AhoMatcher(text_normalizer)

    common_manifest = provider.load_common()
    domain_manifest = provider.load_domain(domain)
    project_manifest = provider.load_project(project_id) if project_id else None
    manifests = [common_manifest, domain_manifest]
    if project_manifest is not None:
        manifests.append(project_manifest)

    validation_reports = [validator.validate_manifest(item) for item in manifests]
    for report in validation_reports:
        validator.ensure_valid(report)

    merged_lexicon = merger.merge(common_manifest, domain_manifest, project_manifest)
    merged_report = validator.validate_merged(merged_lexicon)
    validator.ensure_valid(merged_report)
    compiled_lexicon = matcher.compile(merged_lexicon)
    pipeline = NormalizationPipeline(
        text_normalizer=text_normalizer,
        matcher=matcher,
        resolver=LongestMatchResolver(),
        synonym_mapper=SynonymMapper(),
    )
    evaluation = evaluate_all(
        load_cases(cases_path),
        normalizer=lambda text: pipeline.run(text, compiled_lexicon),
    )
    summary = evaluation["summary"]
    passed = (
        summary["precision"] >= minimum_precision
        and summary["recall"] >= minimum_recall
        and summary["f1"] >= minimum_f1
    )
    warnings = [
        issue.model_dump(mode="json")
        for report in (*validation_reports, merged_report)
        for issue in report.warnings
    ]
    return {
        "ready_for_publish": passed,
        "merged_fingerprint": merged_lexicon.version_set.merged_fingerprint,
        "versions": merged_lexicon.version_set.model_dump(mode="json"),
        "thresholds": {
            "minimum_precision": minimum_precision,
            "minimum_recall": minimum_recall,
            "minimum_f1": minimum_f1,
        },
        "validation_warnings": warnings,
        "evaluation": evaluation,
    }


def main() -> None:
    """运行发布检查，并在不满足闸门时返回非零退出码。"""
    parser = argparse.ArgumentParser(description="检查术语库是否满足发布条件")
    parser.add_argument("--lexicon-root", type=Path, default=DEFAULT_LEXICON_ROOT, help="术语库根目录")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES_PATH, help="评估用例路径")
    parser.add_argument("--domain", default="project_management", help="业务域标识")
    parser.add_argument("--project-id", default=None, help="可选项目标识")
    args = parser.parse_args()

    report = run_release_check(
        lexicon_root=args.lexicon_root,
        cases_path=args.cases,
        domain=args.domain,
        project_id=args.project_id,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["ready_for_publish"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

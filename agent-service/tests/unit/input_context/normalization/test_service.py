"""用户输入归一化服务与兼容边界测试。"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from app.input_context.normalization import create_default_normalization_service
from app.input_context.normalization.lexicon.json_provider import LexiconLoadError
from app.input_context.normalization.lexicon.merger import LexiconMergeError

SERVICE_ROOT = Path(__file__).resolve().parents[4]
LEXICON_ROOT = SERVICE_ROOT / "resources" / "lexicons"


def test_longest_match_keeps_api_key_instead_of_nested_api() -> None:
    result = create_default_normalization_service().normalize_query(
        "请检查 API Key 是否泄露"
    )

    assert result.normalized_terms == ("明文凭据",)
    assert result.matches[0].matched_text == "API Key"


def test_repeated_aliases_keep_matches_and_deduplicate_canonical_term() -> None:
    result = create_default_normalization_service().normalize_query(
        "SQL注入和拼接 SQL 都需要修复"
    )

    assert result.normalized_terms.count("SQL 注入") == 1
    assert [item.canonical for item in result.matches].count("SQL 注入") == 2


def test_nfkc_match_preserves_original_character_range() -> None:
    result = create_default_normalization_service().normalize_query("ＡＰＩ接口")

    match = result.matches[0]
    assert match.canonical == "API"
    assert match.matched_text == "ＡＰＩ"
    assert (match.start, match.end) == (0, 2)
    assert result.matches[1].matched_text == "接口"
    assert (result.matches[1].start, result.matches[1].end) == (3, 4)


def test_missing_project_lexicon_falls_back_to_common_and_domain() -> None:
    result = create_default_normalization_service().normalize_query(
        "当前完成度",
        project_id="missing-project",
    )

    assert "项目进度" in result.normalized_terms
    assert result.lexicon_version_set.project_version is None


def test_project_lexicon_requires_explicit_override_and_takes_priority(
    tmp_path: Path,
) -> None:
    shutil.copyfile(LEXICON_ROOT / "common.json", tmp_path / "common.json")
    shutil.copyfile(
        LEXICON_ROOT / "project_management.json",
        tmp_path / "project_management.json",
    )
    projects = tmp_path / "projects"
    projects.mkdir()
    (projects / "42.json").write_text(
        json.dumps(
            {
                "lexicon_id": "project-42",
                "version": "1.0.0",
                "scope": "project",
                "scope_id": "42",
                "status": "published",
                "description": "项目专属术语",
                "entries": [
                    {
                        "term_id": "project-api",
                        "canonical": "项目接口",
                        "aliases": ["接口"],
                        "category": "project",
                        "tags": [],
                        "priority": 30,
                        "enabled": True,
                        "source": "manual",
                        "override_term_id": "api",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = create_default_normalization_service(tmp_path).normalize_query(
        "检查接口",
        project_id="42",
    )

    assert result.normalized_terms == ("项目接口",)
    assert result.lexicon_version_set.project_lexicon_id == "project-42"


def test_project_lexicon_conflict_without_explicit_override_is_blocked(
    tmp_path: Path,
) -> None:
    shutil.copyfile(LEXICON_ROOT / "common.json", tmp_path / "common.json")
    shutil.copyfile(
        LEXICON_ROOT / "project_management.json",
        tmp_path / "project_management.json",
    )
    projects = tmp_path / "projects"
    projects.mkdir()
    (projects / "42.json").write_text(
        json.dumps(
            {
                "lexicon_id": "project-42",
                "version": "1.0.0",
                "scope": "project",
                "scope_id": "42",
                "status": "published",
                "description": "包含未声明覆盖的冲突词条",
                "entries": [
                    {
                        "term_id": "project-api",
                        "canonical": "项目接口",
                        "aliases": ["接口"],
                        "category": "project",
                        "tags": [],
                        "priority": 30,
                        "enabled": True,
                        "source": "manual",
                        "override_term_id": None,
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    with pytest.raises(LexiconMergeError):
        create_default_normalization_service(tmp_path).normalize_query(
            "检查接口",
            project_id="42",
        )


def test_runtime_validation_blocks_missing_required_lexicons(tmp_path: Path) -> None:
    service = create_default_normalization_service(tmp_path)

    with pytest.raises(LexiconLoadError):
        service.validate_runtime()

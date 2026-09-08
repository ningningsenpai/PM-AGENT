"""用户词库版本切换、最长匹配和隔离缓存验证。"""

from app.modules.chat.context.lexicon import learned_terms


def term(alias, canonical, version=1):
    return {
        "id": "1",
        "kind": "term",
        "sourceMessageId": "10",
        "version": version,
        "attributes": {"aliases": [alias], "canonical": canonical},
    }


def test_longest_and_version_cache():
    terms = [term("工单", "业务单据"), {**term("星河工单", "星河工单台"), "id": "2"}]
    assert learned_terms(1, 11, "星河工单的进度", terms) == ["星河工单台"]
    assert learned_terms(
        1, 11, "星河工单的进度", [term("星河工单", "星河二期", 2)]
    ) == ["星河二期"]
    assert learned_terms(2, 11, "星河工单的进度", []) == []


def test_ambiguous_alias_not_silently_chosen():
    assert (
        learned_terms(
            1,
            11,
            "工单",
            [term("工单", "工单台"), {**term("工单", "报修单"), "id": "2"}],
        )
        == []
    )

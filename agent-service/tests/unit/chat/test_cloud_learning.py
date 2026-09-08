"""云端权威读取、草稿确认和故障恢复的业务回归。"""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.core.errors import AppException
from app.modules.chat.context.models import AgentContextChange, AgentContextEntry
from app.modules.chat.context.schemas import UpdateEntry
from app.modules.chat.conversation.schemas import CreateConversation
from app.modules.chat.learning.schemas import ConfirmDraft, EditDraft, RefineDraft
from app.modules.chat.learning.service import new_id
from app.project_context.specification.schemas import ProjectSpecificationDocument
from tests.unit.chat.test_persistence import (  # noqa: F401
    candidate,
    services as services,
)

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


async def draft_for(services, output):
    conversation = await services.conversations.create(
        1, CreateConversation(projectId="11")
    )
    return await services.learning.create_draft(
        1,
        11,
        conversation.id,
        new_id(),
        output,
        [
            {
                "id": "100",
                "content": "；".join(c.source_quote for c in output.candidates),
            }
        ],
    )


def confirmation(draft):
    return ConfirmDraft(
        version=draft["version"], candidateIds=[c["id"] for c in draft["candidates"]]
    )


async def test_migration_retains_history_and_stops_reading_sql_body(services):
    await services.contexts.scopes(1, 11)
    row = await services.context_repo.add(
        AgentContextEntry(
            id=88,
            user_id=1,
            project_id=11,
            scope_key="1:11",
            kind="short_memory",
            canonical_key="abc",
            content="本周核对部署",
            attributes={"key": "本周事项", "sourceQuote": "核对部署"},
            status="active",
            version=3,
            source_message_id=100,
            expires_at=datetime.now(UTC).replace(tzinfo=None) + timedelta(days=1),
        )
    )
    await services.context_repo.add(
        AgentContextChange(
            id=99,
            entry_id=88,
            version=3,
            before={"content": "旧值"},
            after={"content": row.content},
            reason="历史纠正",
            source_message_id=100,
        )
    )
    await services.session.commit()
    entries = await services.contexts.list_entries(1, 11)
    assert entries[0]["version"] == 3 and entries[0]["sourceMessageId"] == "100"
    assert (await services.contexts.changes(1, 11, 88))[0]["reason"] == "历史纠正"
    services.context_repo.entries = AsyncMock(
        side_effect=AssertionError("已迁移后不能再读取 SQL 正文")
    )
    assert (await services.contexts.list_entries(1, 11))[0]["content"] == "本周核对部署"
    request = UpdateEntry(
        projectId="11",
        version=3,
        reason="用户到期设置",
        expiresAt=(datetime.now(UTC) - timedelta(seconds=1)).isoformat(),
    )
    result = await services.contexts.update_entry(1, 88, request, "expire")
    assert result["version"] == 4 and row.version == 3
    assert await services.contexts.list_entries(1, 11) == []
    assert (await services.contexts.update_entry(1, 88, request, "expire"))[
        "version"
    ] == 4


async def test_partial_publication_recovers_only_failed_scope(services):
    output = candidate("请记住，我偏好中文", kind="habit", scope="user", key="语言")
    output.candidates += candidate().candidates
    draft = await draft_for(services, output)
    original_write = services.contexts.storage.compare_and_put

    def fail_project(location, content, etag):
        if location.object_key == "PM-AGENT/1/11/system/context/manifest.json":
            from app.core.errors import ErrorCode

            raise AppException(ErrorCode.FILE_STORAGE_ERROR, "模拟项目发布失败")
        return original_write(location, content, etag)

    services.contexts.storage.compare_and_put = fail_project
    partial = await services.learning.confirm(1, 11, draft["id"], confirmation(draft))
    assert (
        partial["state"] == "partial" and partial["publications"]["1:user"]["published"]
    )
    assert len(await services.contexts.list_entries(1, 11)) == 1
    user_version = (await services.contexts.versions(1, 11))["1:user"]
    services.contexts.storage.compare_and_put = original_write
    recovered = await services.learning.confirm(1, 11, draft["id"], confirmation(draft))
    assert (
        recovered["state"] == "published"
        and len(await services.contexts.list_entries(1, 11)) == 2
    )
    assert (await services.contexts.versions(1, 11))["1:user"] == user_version


async def test_stale_draft_requires_rebase_and_reconfirmation(services):
    first = await draft_for(services, candidate())
    second = await draft_for(services, candidate("确认上线日期为十月八日"))
    await services.learning.confirm(1, 11, first["id"], confirmation(first))
    with pytest.raises(AppException, match="正式内容已更新"):
        await services.learning.confirm(1, 11, second["id"], confirmation(second))
    rebased = await services.learning.rebase(1, 11, second["id"], 1)
    assert rebased["version"] == 2 and len(rebased["existing"]) == 1
    with pytest.raises(AppException, match="版本"):
        await services.learning.confirm(1, 11, second["id"], confirmation(second))
    with pytest.raises(AppException, match="冲突"):
        await services.learning.confirm(1, 11, second["id"], confirmation(rebased))


async def test_feedback_is_durable_and_changes_only_selected_candidates(services):
    output = candidate()
    output.candidates += candidate(
        "请记住，我偏好中文", kind="habit", scope="user", key="语言"
    ).candidates
    draft = await draft_for(services, output)
    first, untouched = draft["candidates"]

    async def generate(prompt, _schema):
        assert not services.session.in_transaction()
        assert "请记住，我偏好中文" not in prompt
        return candidate("请记住，项目上线日期是 10 月 1 日", conditions=["正式发布"])

    services.learning.generator = SimpleNamespace(
        generate=AsyncMock(side_effect=generate)
    )
    run = await services.learning.refine(
        1,
        11,
        draft["id"],
        RefineDraft(
            version=1,
            candidateIds=[first["id"]],
            feedback="这只是正式发布时间，请加上适用条件",
        ),
        "feedback-one",
        "trace",
    )
    assert run["status"] == "success"
    current = await services.learning.get(1, 11, draft["id"])
    assert untouched in current["candidates"] and current["version"] == 3
    assert current["feedback"][0]["text"] == "这只是正式发布时间，请加上适用条件"
    assert await services.contexts.list_entries(1, 11) == []
    assert len(current["history"]) == 2


async def test_manual_edit_skips_model_and_same_condition_conflict_is_blocked(services):
    output = candidate(
        "确认回答使用中文",
        kind="habit",
        scope="user",
        key="回答语言",
        conditions=["日常问答"],
    )
    output.candidates += candidate(
        "确认回答使用英文",
        kind="habit",
        scope="user",
        key="回答语言",
        conditions=["日常问答"],
    ).candidates
    draft = await draft_for(services, output)
    assert len((await services.learning.get(1, 11, draft["id"]))["conflicts"]) == 1
    draft["candidates"][1]["proposal"].update(
        relatedEntryIds=[draft["candidates"][0]["id"]], coexistReason="是两条不同规则"
    )
    edited = await services.learning.edit(
        1,
        11,
        draft["id"],
        EditDraft(version=1, candidates=draft["candidates"], reason="确认共存关系"),
    )
    with pytest.raises(AppException, match="冲突"):
        await services.learning.confirm(1, 11, draft["id"], confirmation(edited))
    edited["candidates"][1]["proposal"]["conditions"] = ["对外英文报告"]
    revised = await services.learning.edit(
        1,
        11,
        draft["id"],
        EditDraft(version=2, candidates=edited["candidates"], reason="区分适用场景"),
    )
    assert (await services.learning.confirm(1, 11, draft["id"], confirmation(revised)))[
        "state"
    ] == "published"
    assert services.learning.generator is None


async def test_file_refresh_uses_same_manifest_and_preserves_human_correction(services):
    doc = ProjectSpecificationDocument.empty(11).model_dump(mode="json")
    rule = {
        "id": "language",
        "scope": "项目",
        "status": "active",
        "confidence": "high",
        "source_refs": [],
        "created_at": datetime.now(UTC).isoformat(),
        "updated_at": datetime.now(UTC).isoformat(),
        "rule": "注释使用中文",
    }
    doc["project_specification"]["coding_rules"] = [rule]
    snapshot, _ = await services.contexts.specification_snapshot(1, 11)
    await services.contexts.publish_specification(1, 11, snapshot, doc)
    entry = (await services.contexts.list_entries(1, 11))[0]
    await services.contexts.update_entry(
        1,
        int(entry["id"]),
        UpdateEntry(
            projectId="11",
            version=1,
            content="代码注释统一使用简体中文",
            reason="用户明确规范",
        ),
        "edit-rule",
    )
    snapshot, _ = await services.contexts.specification_snapshot(1, 11)
    rule["rule"] = "代码注释使用英文"
    await services.contexts.publish_specification(1, 11, snapshot, doc)
    current = await services.contexts.list_entries(1, 11)
    assert (
        current[0]["content"] == "代码注释统一使用简体中文"
        and current[0]["version"] == 2
    )
    assert "保留人工版本" in (await services.contexts.changes(1, 11))[0]["reason"]
    with pytest.raises(AppException, match="基础版本"):
        await services.contexts.publish_specification(
            1, 11, snapshot, {**doc, "updated_at": datetime.now(UTC).isoformat()}
        )

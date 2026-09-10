"""云端权威读取、草稿确认和故障恢复的业务回归。"""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from app.core.errors import AppException, ErrorCode
from app.modules.chat.context.schemas import UpdateEntry
from app.modules.chat.conversation.models import AgentMessage
from app.modules.chat.conversation.schemas import CreateConversation
from app.modules.chat.learning.schemas import ConfirmDraft, EditDraft, RefineDraft
from app.modules.chat.learning.service import new_id
from app.project_context.specification.schemas import ProjectSpecificationDocument
from tests.unit.chat.test_persistence import (  # noqa: F401
    candidate,
)
from tests.unit.chat.test_persistence import (
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


async def test_fixed_files_are_formal_source_and_sql_context_body_is_not_read(services):
    output = candidate("本周核对部署", kind="short_memory", key="本周事项")
    draft = await draft_for(services, output)
    await services.learning.confirm(1, 11, draft["id"], confirmation(draft))
    entries = await services.contexts.list_entries(1, 11)
    assert entries[0]["content"] == "本周核对部署"
    services.context_repo.entries = AsyncMock(
        side_effect=AssertionError("正式召回不能再读取旧 SQL 上下文正文")
    )
    assert (await services.contexts.list_entries(1, 11))[0]["content"] == "本周核对部署"
    request = UpdateEntry(
        projectId="11",
        version=1,
        reason="用户到期设置",
        expiresAt=(datetime.now(UTC) - timedelta(seconds=1)).isoformat(),
    )
    result = await services.contexts.update_entry(
        1, int(entries[0]["id"]), request, "expire"
    )
    assert result["version"] == 2
    assert await services.contexts.list_entries(1, 11) == []
    assert (
        await services.contexts.update_entry(
            1, int(entries[0]["id"]), request, "expire"
        )
    )["version"] == 2


async def test_partial_publication_recovers_only_failed_scope(services):
    output = candidate("请记住，我偏好中文", kind="habit", scope="user", key="语言")
    output.candidates += candidate().candidates
    draft = await draft_for(services, output)
    original_write = services.contexts.storage.compare_and_put

    def fail_project(location, content, etag):
        if location.object_key.endswith("system/long_term_memory.json"):
            from app.core.errors import ErrorCode

            raise AppException(ErrorCode.FILE_STORAGE_ERROR, "模拟项目发布失败")
        return original_write(location, content, etag)

    services.contexts.storage.compare_and_put = fail_project
    partial = await services.learning.confirm(1, 11, draft["id"], confirmation(draft))
    assert (
        partial["state"] == "partial"
        and partial["publications"]["user_habits/work.json"]["published"]
    )
    assert len(await services.contexts.list_entries(1, 11)) == 1
    user_version = (await services.contexts.versions(1, 11))["user_habits/work.json"]
    services.contexts.storage.compare_and_put = original_write
    recovered = await services.learning.confirm(1, 11, draft["id"], confirmation(draft))
    assert (
        recovered["state"] == "applied"
        and len(await services.contexts.list_entries(1, 11)) == 2
    )
    assert (await services.contexts.versions(1, 11))[
        "user_habits/work.json"
    ] == user_version


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
    ] == "applied"
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
    assert (await services.contexts.changes(1, 11))[0]["reason"] == "用户明确规范"
    with pytest.raises(AppException, match="基础版本"):
        await services.contexts.publish_specification(
            1, 11, snapshot, {**doc, "updated_at": datetime.now(UTC).isoformat()}
        )


async def test_short_memory_promotion_recovers_after_old_file_removal_failure(services):
    draft = await draft_for(
        services,
        candidate("本周完成发布", kind="short_memory", key="本周事项"),
    )
    await services.learning.confirm(1, 11, draft["id"], confirmation(draft))
    entry = (await services.contexts.list_entries(1, 11))[0]
    request = UpdateEntry(
        projectId="11",
        version=1,
        kind="long_memory",
        reason="转为长期项目约定",
    )
    original_apply = services.contexts.fixed.apply
    interrupted = False

    async def fail_old_file_once(user_id, project_id, path, changes, etag):
        nonlocal interrupted
        if path == "short_term_memory.json" and not interrupted:
            interrupted = True
            raise AppException(ErrorCode.FILE_STORAGE_ERROR, "模拟旧文件移除失败")
        return await original_apply(user_id, project_id, path, changes, etag)

    services.contexts.fixed.apply = fail_old_file_once
    with pytest.raises(AppException, match="移除失败"):
        await services.contexts.update_entry(1, int(entry["id"]), request, "promote")
    services.contexts.fixed.apply = original_apply

    recovered = await services.contexts.update_entry(
        1,
        int(entry["id"]),
        request,
        "promote",
    )
    entries = await services.contexts.list_entries(1, 11)
    assert recovered["kind"] == "long_memory"
    assert len(entries) == 1 and entries[0]["kind"] == "long_memory"
    assert entries[0]["version"] == 2


async def test_durable_draft_recovers_failed_run_without_model_replay(services):
    conversation = await services.conversations.create(
        1, CreateConversation(projectId="11")
    )
    conversation_id = conversation.id
    output = candidate()
    services.session.add(
        AgentMessage(
            id=100,
            conversation_id=conversation_id,
            role="user",
            content=output.candidates[0].content,
            run_id=1,
        )
    )
    await services.session.commit()
    services.learning.generator = SimpleNamespace(
        generate=AsyncMock(return_value=output)
    )
    finish = services.runs.finish
    interrupted = False

    async def fail_first_result(*args, **kwargs):
        nonlocal interrupted
        if not interrupted:
            interrupted = True
            raise RuntimeError("模拟云端草稿已落盘，但数据库完成记录失败")
        return await finish(*args, **kwargs)

    services.runs.finish = fail_first_result
    failed = await services.learning.learn(1, conversation_id, "learn-once", "trace")
    assert failed["status"] == "failed"
    assert len(await services.learning.list(1, 11)) == 1
    recovered = await services.learning.learn(1, conversation_id, "learn-once", "trace")
    assert recovered["status"] == "success" and recovered["runId"] == failed["runId"]
    assert recovered["result"]["processedMessages"] == 1
    next_run = await services.learning.learn(1, conversation_id, "learn-next", "trace")
    assert next_run["result"]["processedMessages"] == 0
    assert services.learning.generator.generate.await_count == 1
    assert await services.contexts.list_entries(1, 11) == []


async def test_lost_draft_receipt_does_not_overwrite_later_manual_edit(services):
    draft = await draft_for(services, candidate())
    save = services.learning.drafts.save

    async def fail_receipt(value, etag):
        if value["state"] == "applied":
            raise AppException(ErrorCode.FILE_STORAGE_ERROR, "模拟发布回执未保存")
        return await save(value, etag)

    services.learning.drafts.save = fail_receipt
    with pytest.raises(AppException, match="回执"):
        await services.learning.confirm(1, 11, draft["id"], confirmation(draft))
    assert (await services.learning.get(1, 11, draft["id"]))["state"] == "updating"
    entry = (await services.contexts.list_entries(1, 11))[0]
    await services.contexts.update_entry(
        1,
        int(entry["id"]),
        UpdateEntry(
            projectId="11",
            version=1,
            content="上线调整至 10 月 8 日",
            reason="后续人工纠正",
        ),
        "later-edit",
    )
    version = (await services.contexts.versions(1, 11))["long_term_memory.json"]
    services.learning.drafts.save = save
    recovered = await services.learning.confirm(1, 11, draft["id"], confirmation(draft))
    assert recovered["state"] == "partial"
    current = (await services.contexts.list_entries(1, 11))[0]
    assert current["version"] == 2 and current["content"] == "上线调整至 10 月 8 日"
    assert (await services.contexts.versions(1, 11))["long_term_memory.json"] == version


async def test_partial_rebase_moves_only_unpublished_scope_to_new_draft(services):
    output = candidate("偏好中文", kind="habit", scope="user", key="语言")
    output.candidates += candidate().candidates
    draft = await draft_for(services, output)
    services.contexts.storage.fail_suffix = "system/long_term_memory.json"
    partial = await services.learning.confirm(1, 11, draft["id"], confirmation(draft))
    assert partial["state"] == "partial"
    user_version = (await services.contexts.versions(1, 11))["user_habits/work.json"]
    services.contexts.storage.fail_suffix = None
    concurrent = await draft_for(
        services, candidate("开发使用 Python", kind="long_memory", key="技术栈")
    )
    await services.learning.confirm(1, 11, concurrent["id"], confirmation(concurrent))
    rebased = await services.learning.rebase(1, 11, draft["id"], 1)
    assert rebased["id"] != draft["id"] and rebased["parentDraftId"] == draft["id"]
    assert [c["proposal"]["scope"] for c in rebased["candidates"]] == ["project"]
    assert (await services.learning.rebase(1, 11, draft["id"], 1))["id"] == rebased[
        "id"
    ]
    with pytest.raises(AppException, match="新的草稿"):
        await services.learning.confirm(1, 11, draft["id"], confirmation(draft))
    assert (
        await services.learning.confirm(1, 11, rebased["id"], confirmation(rebased))
    )["state"] == "applied"
    assert (await services.contexts.versions(1, 11))[
        "user_habits/work.json"
    ] == user_version
    assert len(await services.contexts.list_entries(1, 11)) == 3


async def test_learning_does_not_create_new_context_version_objects(services):
    draft = await draft_for(services, candidate())
    await services.learning.confirm(1, 11, draft["id"], confirmation(draft))
    keys = [key for _bucket, key in services.contexts.storage.data]
    assert any(key.endswith("system/long_term_memory.json") for key in keys)
    assert not any("/context/manifest.json" in key for key in keys)
    assert not any("/context/versions/" in key for key in keys)
    assert not any("/context/drafts/" in key for key in keys)


async def test_feedback_split_resolves_server_ids_and_requires_complete_selection(
    services,
):
    draft = await draft_for(
        services,
        candidate("请记住，回答使用中文", kind="habit", scope="user", key="回答语言"),
    )
    feedback_text = "中文用于日常讨论，英文用于对外报告，这两条分别保留。"

    async def generate(_prompt, _schema):
        current, _ = await services.learning.drafts.load(1, 11, draft["id"])
        feedback_id = current["feedback"][-1]["id"]
        output = candidate(
            "日常讨论使用中文",
            kind="habit",
            scope="user",
            key="回答语言",
            sourceMessageId=feedback_id,
            sourceQuote=feedback_text,
            conditions=["日常讨论"],
            coexistReason=feedback_text,
            coexistGroup="语言按场景拆分",
        )
        output.candidates += candidate(
            "对外报告使用英文",
            kind="habit",
            scope="user",
            key="回答语言",
            sourceMessageId=feedback_id,
            sourceQuote=feedback_text,
            conditions=["对外报告"],
            coexistReason=feedback_text,
            coexistGroup="语言按场景拆分",
        ).candidates
        return output

    services.learning.generator = SimpleNamespace(
        generate=AsyncMock(side_effect=generate)
    )
    run = await services.learning.refine(
        1,
        11,
        draft["id"],
        RefineDraft(
            version=1,
            candidateIds=[draft["candidates"][0]["id"]],
            feedback=feedback_text,
        ),
        "split",
        "trace",
    )
    assert run["status"] == "success"
    updated = await services.learning.get(1, 11, draft["id"])
    left, right = updated["candidates"]
    assert left["proposal"]["relatedEntryIds"] == [right["id"]]
    assert right["proposal"]["relatedEntryIds"] == [left["id"]]
    with pytest.raises(AppException, match="未选中"):
        await services.learning.confirm(
            1,
            11,
            draft["id"],
            ConfirmDraft(version=updated["version"], candidateIds=[left["id"]]),
        )
    result = await services.learning.confirm(1, 11, draft["id"], confirmation(updated))
    assert result["state"] == "applied"
    entries = await services.contexts.list_entries(1, 11)
    assert len(entries) == 2 and {e["sourceMessageId"] for e in entries} == {None}
    assert {e["attributes"]["sourceType"] for e in entries} == {"user_feedback"}


async def test_relations_to_replacement_candidates_use_the_effective_entry_id(services):
    existing = await draft_for(
        services,
        candidate(
            "请记住，日常回答使用中文", kind="habit", scope="user", key="回答语言"
        ),
    )
    await services.learning.confirm(1, 11, existing["id"], confirmation(existing))
    entry = (await services.contexts.list_entries(1, 11))[0]
    output = candidate(
        "日常讨论使用中文",
        kind="habit",
        scope="user",
        key="回答语言",
        conditions=["日常讨论"],
        replacesEntryId=entry["id"],
    )
    output.candidates += candidate(
        "对外报告使用英文",
        kind="habit",
        scope="user",
        key="回答语言",
        conditions=["对外报告"],
        coexistReason="区分讨论和报告",
    ).candidates
    draft = await draft_for(services, output)
    draft["candidates"][1]["proposal"]["relatedEntryIds"] = [
        draft["candidates"][0]["id"]
    ]
    updated = await services.learning.edit(
        1,
        11,
        draft["id"],
        EditDraft(
            version=1, candidates=draft["candidates"], reason="人工确认按场景拆分"
        ),
    )
    await services.learning.confirm(1, 11, draft["id"], confirmation(updated))
    entries = await services.contexts.list_entries(1, 11)
    other = next(e for e in entries if e["id"] != entry["id"])
    assert other["relatedEntryIds"] == [entry["id"]]

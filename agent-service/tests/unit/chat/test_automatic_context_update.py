"""验证多维识别结果只通过 MinIO 固定文件生效。"""

import pytest

from app.modules.chat.context.automatic_update import AutomaticContextUpdateService
from app.modules.chat.conversation.schemas import CreateConversation
from app.modules.chat.request_understanding.service import RequestUnderstandingService

pytestmark = pytest.mark.anyio
pytest_plugins = ("tests.unit.chat.test_persistence",)


@pytest.fixture
def anyio_backend():
    return "asyncio"


def updater(services):
    return AutomaticContextUpdateService(
        services.contexts,
        services.learning.drafts.repository,
    )


async def test_explicit_rule_updates_split_minio_file_and_manifest(services):
    conversation = await services.conversations.create(
        1, CreateConversation(projectId="11")
    )
    message = "请把这条设置为本项目规则：所有 API 响应必须包含 traceId。"
    plan = RequestUnderstandingService().analyze(message)

    result = await updater(services).apply(
        user_id=1,
        project_id=11,
        conversation_id=conversation.id,
        message_id=501,
        message=message,
        plan=plan,
    )

    assert result["status"] == "applied"
    assert result["targets"][0]["path"] == "project_specification/coding_rules.json"
    section, _ = await services.contexts.fixed.read(
        1, 11, "project_specification/coding_rules.json"
    )
    manifest, _ = await services.contexts.fixed.read(
        1, 11, "project_specification.json"
    )
    assert section["managed_rules"][0]["rule"] == message
    assert manifest["sections"]["coding_rules"]["item_count"] == 1
    assert manifest["sections"]["coding_rules"]["content_hash"]


async def test_project_preference_is_applied_and_isolated_by_project(services):
    conversation = await services.conversations.create(
        1, CreateConversation(projectId="11")
    )
    message = "以后回答项目进度时请给出详细的 Markdown 列表。"
    plan = RequestUnderstandingService().analyze(message)

    result = await updater(services).apply(
        user_id=1,
        project_id=11,
        conversation_id=conversation.id,
        message_id=502,
        message=message,
        plan=plan,
    )

    assert result["status"] == "applied"
    assert result["targets"][0]["path"] == "user_habits/specification.json"
    entries = await services.contexts.list_entries(1, 11, kind="habit")
    assert [entry["content"] for entry in entries] == [message]
    assert await services.contexts.list_entries(1, 12, kind="habit") == []


async def test_uncertain_preference_creates_only_confirmation_draft(services):
    conversation = await services.conversations.create(
        1, CreateConversation(projectId="11")
    )
    message = "我觉得以后也许可以使用表格回答项目进度。"
    plan = RequestUnderstandingService().analyze(message)

    result = await updater(services).apply(
        user_id=1,
        project_id=11,
        conversation_id=conversation.id,
        message_id=503,
        message=message,
        plan=plan,
    )

    assert result["status"] == "pending_confirmation"
    assert result["targets"] == []
    assert result["draftId"]
    assert await services.contexts.list_entries(1, 11, kind="habit") == []
    drafts = await services.learning.list(1, 11, conversation.id)
    assert len(drafts) == 1
    assert drafts[0]["state"] == "pending"
    assert drafts[0]["candidates"][0]["proposal"]["content"] == message

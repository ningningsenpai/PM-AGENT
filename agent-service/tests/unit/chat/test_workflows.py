"""学习游标、快照重试和报告引用边界的业务测试。"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from app.modules.chat.conversation.models import AgentMessage
from app.modules.chat.conversation.schemas import CreateConversation, SendMessage
from app.modules.chat.learning.schemas import ConfirmDraft
from app.modules.chat.learning.service import new_id
from app.modules.report.repository import ReportRepository
from app.modules.report.schemas import GenerateReport, ReportDraft
from app.modules.report.service import ReportService
from tests.unit.chat.test_persistence import (
    candidate,
    confirmed,
    services,  # noqa: F401
)

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


async def test_learn_creates_durable_preview_and_confirms_without_model(services):
    conversation = await services.conversations.create(
        1, CreateConversation(projectId="11")
    )
    await services.conversation_repo.add(
        AgentMessage(
            id=100,
            conversation_id=conversation.id,
            role="user",
            content="请记住，我偏好简洁中文",
            run_id=1,
            protocol=[],
        )
    )
    await services.session.commit()
    output = candidate(
        "请记住，我偏好简洁中文", kind="habit", scope="user", key="回答风格"
    )
    services.learning.generator = SimpleNamespace(
        generate=AsyncMock(return_value=output)
    )
    first = await services.learning.learn(1, conversation.id, "learn-one", "trace")
    assert first["status"] == "success" and first["result"]["processedMessages"] == 1
    assert first["result"]["candidateCount"] == 1
    assert await services.contexts.list_entries(1, 11) == []
    drafts = await services.learning.list(1, 11, conversation.id)
    assert len(drafts) == 1 and drafts[0]["state"] == "pending"
    same = await services.learning.learn(1, conversation.id, "learn-one", "trace")
    assert same["runId"] == first["runId"]
    draft = drafts[0]
    request = ConfirmDraft(version=1, candidateIds=[draft["candidates"][0]["id"]])
    result = await services.learning.confirm(1, 11, draft["id"], request)
    assert result["state"] == "applied"
    assert (await services.learning.confirm(1, 11, draft["id"], request))[
        "publications"
    ] == result["publications"]
    assert len(await services.contexts.list_entries(1, 11)) == 1
    assert await services.context_repo.entries(1, 11) == []
    second = await services.learning.learn(1, conversation.id, "learn-two", "trace")
    assert second["status"] == "success" and second["result"]["processedMessages"] == 0
    services.learning.generator.generate.assert_awaited_once()


async def test_unconfirmed_draft_preserves_active_memory(services):
    original = (
        await confirmed(
            services,
            1,
            11,
            candidate(),
            [{"id": "100", "content": candidate().candidates[0].content}],
            {},
        )
    )[0]
    proposed = candidate(
        "可能要推迟到 10 月 8 日", replacesEntryId=original["id"], confirmed=False
    )
    draft = await services.learning.create_draft(
        1,
        11,
        99,
        new_id(),
        proposed,
        [{"id": "100", "content": proposed.candidates[0].content}],
    )
    current = await services.contexts.list_entries(1, 11)
    assert current[0]["content"] == original["content"] and current[0]["version"] == 1
    assert (await services.learning.get(1, 11, draft["id"]))["state"] == "pending"


async def test_cancelled_chat_retains_run_and_releases_conversation(services):
    conversation = await services.conversations.create(
        1, CreateConversation(projectId="11")
    )
    conversation_id = conversation.id
    agent = SimpleNamespace(chat=AsyncMock(side_effect=asyncio.CancelledError()))
    with pytest.raises(asyncio.CancelledError):
        await services.conversations.send(
            1,
            conversation_id,
            SendMessage(content="查询项目"),
            "cancel-one",
            "trace",
            agent,
        )
    run = await services.run_repo.duplicate(1, "chat", "cancel-one")
    assert run.status == "failed" and "取消" in run.error
    row = await services.conversation_repo.conversation(1, conversation_id)
    assert row.active_run_id is None and row.busy_until is None
    _, fresh = await services.runs.start(
        1, 11, "chat", "after-cancel", {}, "trace", conversation_id
    )
    assert fresh


def report_service(services, evidence_id):
    files = SimpleNamespace(
        list_files=AsyncMock(
            return_value=[
                SimpleNamespace(
                    id=5,
                    relative_path="api.py",
                    status="active",
                    upload_status="success",
                    analysis_status="success",
                    content_hash="abc",
                )
            ]
        ),
        read_evidence=AsyncMock(
            return_value={
                "fileId": 5,
                "logicalPath": "api.py",
                "contentHash": "abc",
                "startLine": 1,
                "endLine": 1,
                "totalLines": 1,
                "text": "1: @app.get('/tickets')",
                "truncated": False,
                "hasMore": False,
                "redacted": False,
            }
        ),
    )
    generator = SimpleNamespace(
        generate=AsyncMock(
            return_value=ReportDraft.model_validate(
                {
                    "title": "开发报告",
                    "claims": [
                        {
                            "text": "存在查询接口",
                            "category": "fact",
                            "evidenceIds": [evidence_id],
                        }
                    ],
                }
            )
        )
    )
    return ReportService(
        ReportRepository(services.session),
        services.contexts.projects,
        files,
        services.contexts,
        services.runs,
        generator,
    )


async def test_report_rejects_invented_evidence_and_saves_failed_run(services):
    service = report_service(services, "不存在的引用")
    result = await service.generate(
        1, 11, GenerateReport(kind="development"), "bad-report", "trace"
    )
    assert result["status"] == "failed" and "不存在" in result["error"]
    assert await service.list(1, 11) == []
    assert (await services.runs.get(1, int(result["runId"])))["status"] == "failed"


async def test_report_verified_references_and_idempotency(services):
    service = report_service(services, "E0001")
    first = await service.generate(
        1, 11, GenerateReport(kind="development"), "report-one", "trace"
    )
    assert first["status"] == "success"
    assert "api.py:1-1" in first["result"]["report"]["markdown"]
    duplicate = await service.generate(
        1, 11, GenerateReport(kind="development"), "report-one", "trace"
    )
    assert duplicate["runId"] == first["runId"]
    service.generator.generate.assert_awaited_once()
    assert len(await service.list(1, 11)) == 1
    assert await service.list(1, 12) == []


async def test_report_corrects_unknown_reference_only_once(services):
    service = report_service(services, "E0001")
    valid = service.generator.generate.return_value
    invalid = valid.model_copy(deep=True)
    invalid.claims[0].evidence_ids = ["E9999"]
    service.generator.generate.side_effect = [invalid, valid]
    result = await service.generate(
        1, 11, GenerateReport(kind="development"), "repair-report", "trace"
    )
    assert result["status"] == "success"
    assert service.generator.generate.await_count == 2
    assert result["events"][0]["invalidEvidenceIds"] == ["E9999"]
    assert "E9999" not in result["result"]["report"]["markdown"]
    service.generator.generate.side_effect = None
    service.generator.generate.return_value = invalid
    failed = await service.generate(
        1, 11, GenerateReport(kind="development"), "still-invalid", "trace"
    )
    assert failed["status"] == "failed"
    assert service.generator.generate.await_count == 4
    assert len(await service.list(1, 11)) == 1

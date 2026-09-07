"""学习游标、快照重试和报告引用边界的业务测试。"""

from types import SimpleNamespace
import asyncio
from unittest.mock import AsyncMock

import pytest
from app.modules.chat.models import AgentMessage
from app.core.errors import AppException
from app.modules.chat.schemas import (
    CreateConversation,
    GenerateReport,
    LearningOutput,
    ReportDraft,
    SendMessage,
)
from app.modules.report.repository import ReportRepository
from app.modules.report.service import ReportService
from tests.unit.chat.test_persistence import services  # noqa: F401
from tests.unit.chat.test_persistence import candidate

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


async def test_learn_commits_once_and_snapshot_failure_can_retry(services):
    conversation = await services.conversations.create(
        1, CreateConversation(projectId="11")
    )
    await services.repo.add(
        AgentMessage(
            id=100,
            conversation_id=conversation.id,
            role="user",
            content="请记住，我偏好简洁中文",
            run_id=1,
            protocol=[],
        )
    )
    await services.repo.session.commit()
    output = LearningOutput.model_validate(
        {
            "candidates": [
                {
                    "kind": "habit",
                    "scope": "user",
                    "key": "表达偏好",
                    "content": "偏好简洁中文",
                    "sourceMessageId": "100",
                    "sourceQuote": "请记住，我偏好简洁中文",
                    "confirmed": True,
                }
            ]
        }
    )
    services.learning.generator = SimpleNamespace(
        generate=AsyncMock(return_value=output)
    )
    services.contexts.storage.put_bytes.side_effect = OSError("模拟发布失败")
    first = await services.learning.learn(1, conversation.id, "learn-one", "trace")
    assert first["status"] == "success"
    assert first["result"]["processedMessages"] == 1
    assert any(
        not result["published"] for result in first["result"]["snapshots"].values()
    )
    same = await services.learning.learn(1, conversation.id, "learn-one", "trace")
    assert same["runId"] == first["runId"]
    services.contexts.storage.put_bytes.side_effect = None
    assert all(
        result["published"]
        for result in (await services.contexts.publish(1, 11)).values()
    )
    second = await services.learning.learn(1, conversation.id, "learn-two", "trace")
    assert second["status"] == "success" and second["result"]["processedMessages"] == 0
    services.learning.generator.generate.assert_awaited_once()
    assert len(await services.contexts.list_entries(1, 11)) == 1


async def test_inferred_memory_remains_pending(services):
    output = LearningOutput.model_validate(
        {
            "candidates": [
                {
                    "kind": "long_memory",
                    "scope": "project",
                    "key": "上线日期",
                    "content": "可能下月上线",
                    "sourceMessageId": "100",
                    "sourceQuote": "可能下月上线",
                    "confirmed": True,
                }
            ]
        }
    )
    await services.learning.apply(
        1, 11, output, [{"id": "100", "content": "可能下月上线"}], {}
    )
    await services.repo.session.commit()
    assert await services.contexts.list_entries(1, 11) == []
    assert (await services.contexts.list_entries(1, 11, effective=False))[0][
        "status"
    ] == "pending"


async def test_unconfirmed_correction_preserves_active_memory(services):
    confirmed = candidate()
    original = (
        await services.learning.apply(
            1,
            11,
            confirmed,
            [{"id": "100", "content": confirmed.candidates[0].content}],
            {},
        )
    )[0]
    await services.repo.session.commit()
    uncertain = "可能要推迟到 10 月 8 日"
    proposed = candidate(uncertain, replacesEntryId=original["id"], confirmed=False)
    with pytest.raises(AppException, match="未经确认"):
        await services.learning.apply(
            1,
            11,
            proposed,
            [{"id": "100", "content": uncertain}],
            {int(original["id"]): 1},
        )
    await services.repo.session.rollback()
    current = await services.contexts.list_entries(1, 11)
    assert len(current) == 1
    assert current[0]["content"] == original["content"]
    assert current[0]["version"] == 1


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
    run = await services.repo.duplicate(1, "chat", "cancel-one")
    assert run.status == "failed" and "取消" in run.error
    row = await services.repo.conversation(1, conversation_id)
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
        ReportRepository(services.repo.session),
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

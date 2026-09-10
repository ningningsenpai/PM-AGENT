"""在真实 SQLAlchemy 会话中验证隔离、纠正、版本和幂等。"""

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.errors import AppException
from app.core.time import shanghai_now_naive
from app.infrastructure.database import Base
from app.modules.chat.context.repository import ContextRepository
from app.modules.chat.context.schemas import UpdateEntry
from app.modules.chat.context.service import ContextService
from app.modules.chat.conversation.repository import ConversationRepository
from app.modules.chat.conversation.schemas import CreateConversation
from app.modules.chat.conversation.service import ConversationService
from app.modules.chat.learning.schemas import ConfirmDraft, LearningOutput
from app.modules.chat.learning.service import LearningService, new_id
from app.modules.chat.runs import service as run_service_module
from app.modules.chat.runs.models import AgentRun
from app.modules.chat.runs.repository import RunRepository
from app.modules.chat.runs.service import RunService
from app.modules.project.models import Project
from app.modules.project_file.analysis.schemas import ProjectFileParseRecovery
from app.modules.user.models import User
from tests.unit.chat.storage_stub import MemoryStorage

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def services():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        session.add_all(
            [
                User(id=1, username="甲", password_hash="x", email="a@test"),
                User(id=2, username="乙", password_hash="x", email="b@test"),
            ]
        )
        session.add_all(
            [
                Project(id=11, owner_user_id=1, project_name="甲项目", status="active"),
                Project(
                    id=12, owner_user_id=1, project_name="另一个项目", status="active"
                ),
                Project(id=21, owner_user_id=2, project_name="乙项目", status="active"),
            ]
        )
        await session.commit()

        class Projects:
            async def get_owned(self, user, project):
                row = await session.get(Project, project)
                if not row or row.owner_user_id != user:
                    from app.core.errors import ErrorCode

                    raise AppException(ErrorCode.FORBIDDEN)
                return row

        context_repo = ContextRepository(session)
        conversation_repo = ConversationRepository(session)
        run_repo = RunRepository(session)
        projects = Projects()
        contexts = ContextService(context_repo, projects, MemoryStorage(), "test")
        runs = RunService(run_repo, projects, conversation_repo)
        conversations = ConversationService(conversation_repo, projects, runs, contexts)
        learning = LearningService(
            context_repo, conversation_repo, conversations, contexts, runs, None
        )
        yield SimpleNamespace(
            session=session,
            context_repo=context_repo,
            conversation_repo=conversation_repo,
            run_repo=run_repo,
            contexts=contexts,
            runs=runs,
            conversations=conversations,
            learning=learning,
        )
    await engine.dispose()


def candidate(content="请记住，项目上线日期是 10 月 1 日", **changes):
    item = dict(
        kind="long_memory",
        scope="project",
        key="上线日期",
        content=content,
        sourceMessageId="100",
        sourceQuote=content,
        confirmed=True,
    )
    item.update(changes)
    return LearningOutput.model_validate({"candidates": [item]})


async def confirmed(services, user, project, output, messages, _versions):
    draft = await services.learning.create_draft(
        user, project, 99, new_id(), output, messages
    )
    result = await services.learning.confirm(
        user,
        project,
        draft["id"],
        ConfirmDraft(version=1, candidateIds=[c["id"] for c in draft["candidates"]]),
    )
    assert result["state"] == "applied"
    return [c["after"] for c in result["plan"]["changes"]]


async def test_correction_and_cross_project_isolation(services):
    first = candidate()
    changed = await confirmed(
        services,
        1,
        11,
        first,
        [{"id": "100", "content": first.candidates[0].content}],
        {},
    )
    await services.session.commit()
    entry = changed[0]
    assert await services.contexts.list_entries(1, 12) == []
    assert await services.contexts.list_entries(2, 21) == []
    new = "更正，上线日期改为 10 月 8 日"
    output = candidate(new, replacesEntryId=entry["id"])
    await confirmed(
        services, 1, 11, output, [{"id": "100", "content": new}], {int(entry["id"]): 1}
    )
    await services.session.commit()
    active = await services.contexts.list_entries(1, 11)
    assert (
        len(active) == 1 and active[0]["version"] == 2 and active[0]["content"] == new
    )
    changes = await services.contexts.changes(1, 11)
    assert changes[0]["before"]["content"] == first.candidates[0].content
    with pytest.raises(AppException):
        await services.contexts.changes(1, 12, int(entry["id"]))


async def test_user_habits_use_current_project_fixed_file_and_expiry(services):
    habit = candidate(
        "请记住，我偏好简洁中文", kind="habit", scope="user", key="回答风格"
    )
    await confirmed(
        services,
        1,
        11,
        habit,
        [{"id": "100", "content": habit.candidates[0].content}],
        {},
    )
    await services.session.commit()
    assert await services.contexts.list_entries(1, 12) == []
    assert await services.contexts.list_entries(2, 21) == []
    short = candidate(
        "确认本周先完成测试",
        kind="short_memory",
        key="本周任务",
        expiresAt=(
            datetime.now(UTC).replace(tzinfo=None) - timedelta(days=1)
        ).isoformat(),
    )
    await confirmed(
        services,
        1,
        11,
        short,
        [{"id": "100", "content": short.candidates[0].content}],
        {},
    )
    await services.session.commit()
    assert len(await services.contexts.list_entries(1, 11)) == 1
    assert len(await services.contexts.list_entries(1, 11, effective=False)) == 2


async def test_quote_and_version_guard(services):
    with pytest.raises(AppException, match="原文"):
        await confirmed(
            services,
            1,
            11,
            candidate(),
            [{"id": "100", "content": "什么时候上线？"}],
            {},
        )
    await services.session.rollback()
    first = candidate()
    entry = (
        await confirmed(
            services,
            1,
            11,
            first,
            [{"id": "100", "content": first.candidates[0].content}],
            {},
        )
    )[0]
    await services.session.commit()
    with pytest.raises(AppException, match="版本"):
        await services.contexts.update_entry(
            1,
            int(entry["id"]),
            UpdateEntry(projectId="11", version=9, status="invalid", reason="用户取消"),
            "version-check",
        )


async def test_idempotency_and_busy_conversation(services):
    conversation = await services.conversations.create(
        1, CreateConversation(projectId="11")
    )
    run, fresh = await services.runs.start(
        1, 11, "chat", "request-1", {"content": "甲"}, "trace", conversation.id
    )
    assert fresh
    run_id = run.id
    same, fresh = await services.runs.start(
        1, 11, "chat", "request-1", {"content": "甲"}, "trace", conversation.id
    )
    assert not fresh and same.id == run.id
    with pytest.raises(AppException, match="不同请求"):
        await services.runs.start(
            1, 11, "chat", "request-1", {"content": "乙"}, "trace", conversation.id
        )
    with pytest.raises(AppException, match="运行中"):
        await services.runs.start(
            1, 11, "chat", "request-2", {}, "trace", conversation.id
        )
    await services.session.rollback()
    await services.runs.finish(run_id, 1, [], {"answer": "完成"})
    _again, fresh = await services.runs.start(
        1, 11, "chat", "request-2", {}, "trace", conversation.id
    )
    assert fresh


async def test_project_run_scope_rejects_parallel_batches_and_releases(services):
    scope = "project-file-parse:11"
    first, fresh = await services.runs.start(
        1,
        11,
        "parse",
        "parse-request-1",
        {"force": False, "fileIds": None},
        "trace",
        exclusive_scope=scope,
    )
    assert fresh
    first_id = first.id
    same, fresh = await services.runs.start(
        1,
        11,
        "parse",
        "parse-request-1",
        {"force": False, "fileIds": None},
        "trace",
        exclusive_scope=scope,
    )
    assert not fresh and same.id == first.id
    with pytest.raises(AppException, match="已有运行中的解析任务"):
        await services.runs.start(
            1,
            11,
            "parse",
            "parse-request-2",
            {"force": True, "fileIds": [1]},
            "trace",
            exclusive_scope=scope,
        )
    await services.session.rollback()
    await services.runs.finish(first_id, 1, [], {"status": "success"})

    second, fresh = await services.runs.start(
        1,
        11,
        "parse",
        "parse-request-2",
        {"force": True, "fileIds": [1]},
        "trace",
        exclusive_scope=scope,
    )
    assert fresh and second.id != first_id


async def test_expired_project_run_scope_can_be_recovered(services):
    scope = "project-file-parse:11"
    first, _fresh = await services.runs.start(
        1,
        11,
        "parse",
        "expired-request",
        {},
        "trace",
        exclusive_scope=scope,
    )
    first.lease_until = datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=1)
    await services.session.commit()

    recovered, fresh = await services.runs.start(
        1,
        11,
        "parse",
        "recovered-request",
        {},
        "trace",
        exclusive_scope=scope,
    )

    assert fresh and recovered.id != first.id
    assert first.status == "failed"
    assert first.active_scope_key is None


async def test_parse_recovery_distinguishes_absent_running_success_and_failed(services):
    absent = await services.runs.recover(1, 11, "parse", "not-created")
    assert absent["status"] == "absent"
    assert absent["retryable"] and absent["retryMode"] == "same_key"
    assert absent["serverTime"].utcoffset() == timedelta(hours=8)
    absent_json = ProjectFileParseRecovery.model_validate(absent).model_dump(
        mode="json", by_alias=True
    )
    assert absent_json["serverTime"].endswith("+08:00")

    running, _fresh = await services.runs.start(
        1,
        11,
        "parse",
        "recover-running",
        {},
        "trace",
        exclusive_scope="project-file-parse:11",
    )
    running_state = await services.runs.recover(1, 11, "parse", "recover-running")
    assert running_state["status"] == "running"
    assert running_state["leaseUntil"] is not None
    assert running_state["serverTime"].utcoffset() == timedelta(hours=8)
    assert running_state["retryMode"] is None

    running.lease_until = shanghai_now_naive() - timedelta(seconds=1)
    await services.session.commit()
    failed = await services.runs.recover(1, 11, "parse", "recover-running")
    assert failed["status"] == "failed"
    assert failed["retryable"] and failed["retryMode"] == "new_key"
    assert running.active_scope_key is None
    await services.runs.finish(
        running.id,
        1,
        [{"stage": "late"}],
        {"status": "success"},
    )
    assert running.status == "failed"
    assert running.result == {}

    success, _fresh = await services.runs.start(
        1,
        11,
        "parse",
        "recover-success",
        {},
        "trace",
        exclusive_scope="project-file-parse:11",
    )
    await services.runs.finish(success.id, 1, [], {"status": "success"})
    recovered = await services.runs.recover(1, 11, "parse", "recover-success")
    assert recovered["status"] == "success"
    assert recovered["result"] == {"status": "success"}
    assert not recovered["retryable"]


@pytest.mark.parametrize("broken_field", ["lease_until", "active_scope_key"])
async def test_parse_recovery_releases_broken_running_lease(services, broken_field):
    running, _fresh = await services.runs.start(
        1,
        11,
        "parse",
        f"broken-{broken_field}",
        {},
        "trace",
        exclusive_scope="project-file-parse:11",
    )
    setattr(running, broken_field, None)
    await services.session.commit()

    first = await services.runs.recover(
        1, 11, "parse", f"broken-{broken_field}"
    )
    original_error = first["error"]
    second = await services.runs.recover(
        1, 11, "parse", f"broken-{broken_field}"
    )

    assert first["status"] == "failed"
    assert first["retryMode"] == "new_key"
    assert running.active_scope_key is None and running.lease_until is None
    assert second["status"] == "failed" and second["error"] == original_error


async def test_startup_cleanup_only_releases_stale_parse_runs(services):
    valid, _fresh = await services.runs.start(
        1,
        11,
        "parse",
        "startup-valid",
        {},
        "trace",
        exclusive_scope="project-file-parse:11",
    )
    expired, _fresh = await services.runs.start(
        1,
        12,
        "parse",
        "startup-expired",
        {},
        "trace",
        exclusive_scope="project-file-parse:12",
    )
    expired.lease_until = shanghai_now_naive() - timedelta(seconds=1)
    missing_lease, _fresh = await services.runs.start(
        2,
        21,
        "parse",
        "startup-missing-lease",
        {},
        "trace",
        exclusive_scope="project-file-parse:21",
    )
    missing_lease.lease_until = None
    missing_scope = AgentRun(
        id=999_001,
        user_id=1,
        project_id=11,
        operation="parse",
        request_key="startup-missing-scope",
        request_hash="hash",
        trace_id="trace",
        active_scope_key=None,
        lease_until=shanghai_now_naive() + timedelta(seconds=60),
        status="running",
        events=[],
        result={},
    )
    services.session.add(missing_scope)
    await services.session.commit()

    released = await services.run_repo.expire_stale_parse_runs(
        shanghai_now_naive()
    )
    await services.session.commit()

    assert released == 3
    assert valid.status == "running" and valid.lease_until is not None
    for stale in (expired, missing_lease, missing_scope):
        await services.session.refresh(stale)
        assert stale.status == "failed"
        assert stale.active_scope_key is None and stale.lease_until is None


async def test_parse_lease_reaper_runs_cleanup_periodically(monkeypatch):
    sleep_count = 0
    cleanup_calls = []
    session_factory = object()

    async def fake_sleep(interval_seconds):
        nonlocal sleep_count
        assert interval_seconds == 30
        sleep_count += 1
        if sleep_count > 1:
            raise asyncio.CancelledError

    async def fake_cleanup(current_session_factory):
        cleanup_calls.append(current_session_factory)
        return 1

    monkeypatch.setattr(run_service_module.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(
        run_service_module,
        "cleanup_stale_parse_runs",
        fake_cleanup,
    )

    with pytest.raises(asyncio.CancelledError):
        await run_service_module.watch_stale_parse_runs(session_factory)

    assert cleanup_calls == [session_factory]

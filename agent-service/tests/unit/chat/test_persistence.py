"""在真实 SQLAlchemy 会话中验证隔离、纠正、版本和幂等。"""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.errors import AppException
from app.infrastructure.database import Base
from app.modules.chat.context.repository import ContextRepository
from app.modules.chat.context.schemas import UpdateEntry
from app.modules.chat.context.service import ContextService
from app.modules.chat.conversation.repository import ConversationRepository
from app.modules.chat.conversation.schemas import CreateConversation
from app.modules.chat.conversation.service import ConversationService
from app.modules.chat.learning.schemas import LearningOutput
from app.modules.chat.learning.service import LearningService
from app.modules.chat.runs.repository import RunRepository
from app.modules.chat.runs.service import RunService
from app.modules.project.models import Project
from app.modules.user.models import User

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
        contexts = ContextService(context_repo, projects, Mock(), "test")
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


async def test_correction_and_cross_project_isolation(services):
    first = candidate()
    changed = await services.learning.apply(
        1, 11, first, [{"id": "100", "content": first.candidates[0].content}], {}
    )
    await services.session.commit()
    entry = changed[0]
    assert await services.contexts.list_entries(1, 12) == []
    assert await services.contexts.list_entries(2, 21) == []
    new = "更正，上线日期改为 10 月 8 日"
    output = candidate(new, replacesEntryId=entry["id"])
    await services.learning.apply(
        1, 11, output, [{"id": "100", "content": new}], {int(entry["id"]): 1}
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


async def test_user_habits_shared_only_with_owner_and_expiry(services):
    habit = candidate(
        "请记住，我偏好简洁中文", kind="habit", scope="user", key="回答风格"
    )
    await services.learning.apply(
        1, 11, habit, [{"id": "100", "content": habit.candidates[0].content}], {}
    )
    await services.session.commit()
    assert len(await services.contexts.list_entries(1, 12)) == 1
    assert await services.contexts.list_entries(2, 21) == []
    short = candidate(
        "确认本周先完成测试",
        kind="short_memory",
        key="本周任务",
        expiresAt=(
            datetime.now(UTC).replace(tzinfo=None) - timedelta(days=1)
        ).isoformat(),
    )
    await services.learning.apply(
        1, 11, short, [{"id": "100", "content": short.candidates[0].content}], {}
    )
    await services.session.commit()
    assert len(await services.contexts.list_entries(1, 11)) == 1
    assert len(await services.contexts.list_entries(1, 11, effective=False)) == 2


async def test_quote_and_version_guard(services):
    with pytest.raises(AppException, match="原文"):
        await services.learning.apply(
            1, 11, candidate(), [{"id": "100", "content": "什么时候上线？"}], {}
        )
    await services.session.rollback()
    first = candidate()
    entry = (
        await services.learning.apply(
            1, 11, first, [{"id": "100", "content": first.candidates[0].content}], {}
        )
    )[0]
    await services.session.commit()
    with pytest.raises(AppException, match="版本"):
        await services.contexts.update_entry(
            1,
            int(entry["id"]),
            UpdateEntry(version=9, status="invalid", reason="用户取消"),
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

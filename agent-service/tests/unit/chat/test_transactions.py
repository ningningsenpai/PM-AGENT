"""验证拆分仓储后的请求装配、事务原子性和运行租约。"""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Annotated
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
from app.infrastructure.database import get_db_session
from app.infrastructure.storage import get_object_storage
from app.modules.chat import dependencies
from app.modules.chat.conversation.models import AgentMessage
from app.modules.chat.conversation.schemas import CreateConversation, SendMessage
from app.modules.chat.learning.schemas import LearningOutput
from app.modules.chat.learning.service import LearningService
from app.modules.project.dependencies import get_project_service
from app.modules.project_file.management.dependencies import get_project_file_service
from app.modules.report import dependencies as report_dependencies
from app.modules.report.service import ReportService
from fastapi import Depends, FastAPI
from tests.unit.chat.test_persistence import (
    services as services,  # noqa: PLC0414 -- 复用带真实事务的 SQLite 夹具。
)

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


async def test_fastapi_composition_shares_request_session(services, monkeypatch):
    app = FastAPI()
    sessions = []

    async def session_dependency():
        sessions.append(services.session)
        yield services.session

    app.dependency_overrides[get_db_session] = session_dependency
    app.dependency_overrides[get_object_storage] = lambda: Mock()
    app.dependency_overrides[get_project_service] = lambda: services.contexts.projects
    app.dependency_overrides[get_project_file_service] = lambda: SimpleNamespace()
    monkeypatch.setattr(dependencies, "get_structured_generator", lambda _: None)
    monkeypatch.setattr(report_dependencies, "get_structured_generator", lambda _: None)

    @app.get("/composition")
    async def composition(
        learning: Annotated[
            LearningService, Depends(dependencies.get_learning_service)
        ],
        reports: Annotated[
            ReportService, Depends(report_dependencies.get_report_service)
        ],
    ):
        repositories = [
            learning.repo,
            learning.message_repo,
            learning.conversations.repo,
            learning.contexts.repo,
            learning.runs.repo,
            learning.runs.conversation_repo,
            reports.repo,
        ]
        return {
            "sameSession": all(
                repo.session is services.session for repo in repositories
            ),
            "sameRunService": learning.runs is reports.runs,
            "sameContextService": learning.contexts is reports.contexts,
            "separateRepositories": learning.repo is not learning.message_repo,
        }

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        result = (await client.get("/composition")).json()
    assert result == {
        "sameSession": True,
        "sameRunService": True,
        "sameContextService": True,
        "separateRepositories": True,
    }
    assert len(sessions) == 1


async def test_learning_failure_rolls_back_entries_cursor_and_scope_version(services):
    conversation = await services.conversations.create(
        1, CreateConversation(projectId="11")
    )
    await services.conversation_repo.add(
        AgentMessage(
            id=100,
            conversation_id=conversation.id,
            role="user",
            content="请记住，上线日期是十月一日",
            run_id=1,
            protocol=[],
        )
    )
    await services.session.commit()
    candidate = {
        "kind": "long_memory",
        "scope": "project",
        "key": "上线日期",
        "content": "上线日期是十月一日",
        "sourceMessageId": "100",
        "sourceQuote": "请记住，上线日期是十月一日",
        "confirmed": True,
    }
    output = LearningOutput.model_validate(
        {
            "candidates": [
                candidate,
                {**candidate, "key": "无效来源", "sourceQuote": "原文不存在这句话"},
            ]
        }
    )

    async def generate(*_args):
        assert not services.session.in_transaction()
        return output

    services.learning.generator = SimpleNamespace(
        generate=AsyncMock(side_effect=generate)
    )
    result = await services.learning.learn(
        1, conversation.id, "rollback-learning", "trace"
    )
    assert result["status"] == "failed"
    assert "原文" in result["error"]
    assert await services.contexts.list_entries(1, 11, effective=False) == []
    row = await services.conversation_repo.conversation(1, conversation.id)
    assert row.learned_message_id == 0
    assert row.active_run_id is None and row.busy_until is None
    scope = await services.context_repo.scope("1:11")
    assert scope is None
    assert not any("/drafts/" in key for _, key in services.contexts.storage.data)


async def test_chat_releases_transaction_before_agent_and_retains_message_link(
    services,
):
    conversation = await services.conversations.create(
        1, CreateConversation(projectId="11")
    )

    async def chat(*_args, **_kwargs):
        assert not services.session.in_transaction()
        return SimpleNamespace(
            answer="本地回答", model="测试模型", tool_calls=[], usage=None
        )

    result = await services.conversations.send(
        1,
        conversation.id,
        SendMessage(content="查看项目资料"),
        "transaction-chat",
        "trace",
        SimpleNamespace(chat=chat),
    )
    assert result["status"] == "success"
    messages = await services.conversations.messages(1, conversation.id)
    assert [message.role for message in messages] == ["user", "assistant"]
    assert {message.request_key for message in messages} == {"transaction-chat"}


async def test_expired_lease_retains_failed_run_and_allows_new_request(services):
    conversation = await services.conversations.create(
        1, CreateConversation(projectId="11")
    )
    run, _ = await services.runs.start(
        1, 11, "chat", "expired", {}, "trace", conversation.id
    )
    run_id = run.id
    row = await services.conversation_repo.conversation(1, conversation.id)
    row.busy_until = datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=1)
    await services.session.commit()
    duplicate, fresh = await services.runs.start(
        1, 11, "chat", "expired", {}, "trace", conversation.id
    )
    assert not fresh and duplicate.id == run_id and duplicate.status == "failed"
    assert "过期" in duplicate.error
    next_run, fresh = await services.runs.start(
        1, 11, "chat", "after-expiry", {}, "trace", conversation.id
    )
    assert fresh and next_run.id != run_id
    assert (
        await services.conversation_repo.conversation(1, conversation.id)
    ).active_run_id == next_run.id

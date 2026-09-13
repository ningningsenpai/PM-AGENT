"""验证拆分仓储后的请求装配、事务原子性和运行租约。"""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Annotated
from unittest.mock import Mock

import httpx
import pytest
from fastapi import Depends, FastAPI

from app.infrastructure.database import get_db_session
from app.infrastructure.storage import get_object_storage
from app.modules.chat import dependencies
from app.modules.chat.conversation.schemas import CreateConversation, SendMessage
from app.modules.chat.learning.service import LearningService
from app.modules.project.dependencies import get_project_service
from app.modules.project_file.management.dependencies import get_project_file_service
from app.modules.report import dependencies as report_dependencies
from app.modules.report.service import ReportService
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

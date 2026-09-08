"""会话自动命名、改名权限及前端消息关联契约回归。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI

from app.core.errors import AppException, install_exception_handlers
from app.core.security import AuthPrincipal, require_principal
from app.modules.chat.assistant_api import router
from app.modules.chat.dependencies import get_conversation_service
from app.modules.chat.models import AgentConversation
from app.modules.chat.schemas import CreateConversation, RenameConversation, SendMessage
from tests.unit.chat.test_persistence import (
    services as services,  # noqa: PLC0414 -- 显式导出共享 pytest 夹具。
)

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


async def test_numbering_survives_rename_and_is_scoped_to_project(services):
    first = await services.conversations.create(1, CreateConversation(projectId="11"))
    assert first.title == "项目对话-1"
    await services.conversations.rename(
        1, first.id, RenameConversation(title="  需求讨论  ")
    )
    second = await services.conversations.create(1, CreateConversation(projectId="11"))
    assert second.title == "项目对话-2"
    assert (
        await services.conversations.create(1, CreateConversation(projectId="12"))
    ).title == "项目对话-1"
    assert (
        await services.conversations.create(2, CreateConversation(projectId="21"))
    ).title == "项目对话-1"
    await services.conversations.rename(
        1, second.id, RenameConversation(title="项目对话-9")
    )
    assert (
        await services.conversations.create(1, CreateConversation(projectId="11"))
    ).title == "项目对话-10"
    saved = await services.conversations.list(1, 11)
    assert next(item for item in saved if item.id == first.id).title == "需求讨论"


async def test_more_than_one_hundred_conversations_are_visible_and_numbered(services):
    services.repo.session.add_all(
        [
            AgentConversation(
                id=1000 + index, user_id=1, project_id=11, title=f"项目对话-{index + 1}"
            )
            for index in range(105)
        ]
    )
    await services.repo.session.commit()
    created = await services.conversations.create(1, CreateConversation(projectId="11"))
    assert created.title == "项目对话-106"
    assert len(await services.conversations.list(1, 11)) == 106
    assert await services.conversations.list(1, 12) == []


async def test_rename_api_validates_title_and_ownership(services):
    app = FastAPI()
    app.include_router(router)
    install_exception_handlers(app)
    actor = 1
    app.dependency_overrides[require_principal] = lambda: AuthPrincipal(
        user_id=actor, jti="测试"
    )
    app.dependency_overrides[get_conversation_service] = lambda: services.conversations
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/agent/conversations", json={"projectId": "11"}
        )
        conversation = response.json()["data"]
        assert conversation["title"] == "项目对话-1"
        assert isinstance(conversation["id"], str)
        url = f"/api/v1/agent/conversations/{conversation['id']}"
        response = await client.patch(url, json={"title": "  项目需求问答  "})
        assert response.json()["data"]["title"] == "项目需求问答"
        for title in ("", "   ", "字" * 129):
            assert (await client.patch(url, json={"title": title})).json()[
                "code"
            ] != 200
        actor = 2
        assert (await client.patch(url, json={"title": "越权修改"})).json()[
            "code"
        ] != 200
        assert (await services.conversations.list(1, 11))[0].title == "项目需求问答"


async def test_persisted_messages_expose_original_request_key(services):
    conversation = await services.conversations.create(
        1, CreateConversation(projectId="11")
    )
    agent = SimpleNamespace(
        chat=AsyncMock(
            return_value=SimpleNamespace(
                answer="测试回答",
                model="本地样例",
                tool_calls=[],
                usage=None,
            )
        )
    )
    await services.conversations.send(
        1,
        conversation.id,
        SendMessage(content="同一问题"),
        "request-one",
        "trace",
        agent,
    )
    await services.conversations.send(
        1,
        conversation.id,
        SendMessage(content="同一问题"),
        "request-two",
        "trace",
        agent,
    )
    messages = await services.conversations.messages(1, conversation.id)
    assert [message.request_key for message in messages if message.role == "user"] == [
        "request-one",
        "request-two",
    ]
    with pytest.raises(AppException):
        await services.conversations.messages(2, conversation.id)

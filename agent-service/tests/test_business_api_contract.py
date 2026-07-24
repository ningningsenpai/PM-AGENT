"""认证、用户、项目 API 的统一响应契约测试。"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.core.security import AuthPrincipal, require_principal
from app.main import app
from app.modules.auth.api import get_auth_service
from app.modules.project.api import get_project_service
from app.modules.user.api import get_user_service
from app.streaming.payloads import ChatResponse


async def _principal() -> AuthPrincipal:
    return AuthPrincipal(user_id=7, jti="contract-jti")


def test_login_should_preserve_json_and_response_contract() -> None:
    service = AsyncMock()
    service.login.return_value = {
        "tokenName": "Authorization",
        "tokenValue": "test-token",
        "user": {"id": 7, "username": "tester", "email": "test@example.com"},
    }
    app.dependency_overrides[get_auth_service] = lambda: service
    try:
        response = TestClient(app).post(
            "/api/v1/auth/login",
            json={"email": "test@example.com", "password": "Password123"},
            headers={"X-Trace-Id": "trace-login"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["code"] == 0
    assert response.json()["traceId"] == "trace-login"
    assert response.json()["data"]["tokenName"] == "Authorization"
    service.login.assert_awaited_once()


def test_user_profile_should_require_current_principal() -> None:
    service = AsyncMock()
    service.get_profile.return_value = {
        "id": 7,
        "username": "tester",
        "email": "test@example.com",
        "status": "enabled",
        "createdAt": "2026-07-24T00:00:00",
        "updatedAt": "2026-07-24T00:00:00",
    }
    app.dependency_overrides[require_principal] = _principal
    app.dependency_overrides[get_user_service] = lambda: service
    try:
        response = TestClient(app).get(
            "/api/v1/users/me",
            headers={"X-Trace-Id": "trace-user"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.json()["code"] == 0
    assert response.json()["data"]["username"] == "tester"
    service.get_profile.assert_awaited_once_with(7)


def test_project_create_should_use_project_name_contract() -> None:
    service = AsyncMock()
    service.create.return_value = {
        "id": 12,
        "projectName": "迁移项目",
        "status": "active",
        "createdAt": "2026-07-24T00:00:00",
        "updatedAt": "2026-07-24T00:00:00",
    }
    app.dependency_overrides[require_principal] = _principal
    app.dependency_overrides[get_project_service] = lambda: service
    try:
        response = TestClient(app).post(
            "/api/v1/projects",
            json={"projectName": "迁移项目"},
            headers={"X-Trace-Id": "trace-project"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.json()["code"] == 0
    assert response.json()["data"]["projectName"] == "迁移项目"
    assert service.create.await_args.args[0] == 7
    assert service.create.await_args.args[1].project_name == "迁移项目"


def test_missing_login_field_should_return_chinese_validation_error() -> None:
    response = TestClient(app).post(
        "/api/v1/auth/login",
        json={"password": "Password123"},
        headers={"X-Trace-Id": "trace-invalid"},
    )

    body = response.json()
    assert response.status_code == 200
    assert body["code"] == 10001
    assert body["message"] == "email：字段不能为空"
    assert body["traceId"] == "trace-invalid"


def _agent_request(user_id: int) -> dict:
    return {
        "trace_id": "trace-agent",
        "conversation_id": 11,
        "messages": [{"role": "user", "content": "项目进展如何？"}],
        "context": {
            "project_id": 12,
            "iteration_id": 1,
            "context_total_usage": 0,
            "task_id": 0,
        },
        "user": {
            "user_id": user_id,
            "tenant_id": 0,
            "user_name": "tester",
        },
        "stream": False,
    }


def test_agent_chat_should_use_authenticated_user() -> None:
    agent = AsyncMock()
    agent.chat.return_value = ChatResponse(
        answer="项目进展正常",
        model="test-model",
        conversation_id=11,
    )
    app.dependency_overrides[require_principal] = _principal
    try:
        with patch(
            "app.api.v1.agent.ProjectChatAgent",
            return_value=agent,
        ):
            response = TestClient(app).post(
                "/api/v1/agent/chat",
                json=_agent_request(7),
                headers={"X-Trace-Id": "trace-agent"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.json()["code"] == 0
    assert response.json()["data"]["answer"] == "项目进展正常"
    agent.chat.assert_awaited_once()


def test_agent_chat_should_reject_forged_user() -> None:
    app.dependency_overrides[require_principal] = _principal
    try:
        response = TestClient(app).post(
            "/api/v1/agent/chat",
            json=_agent_request(8),
            headers={"X-Trace-Id": "trace-agent-forbidden"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.json()["code"] == 20002
    assert response.json()["message"] == "请求用户与登录用户不一致"

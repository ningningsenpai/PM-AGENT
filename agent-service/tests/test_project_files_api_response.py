"""项目文件公开接口契约测试。"""
from __future__ import annotations

from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from app.core.security import AuthPrincipal, require_principal
from app.main import app
from app.modules.project_file.api import get_project_file_analysis_service

_TRACE_ID = "trace-file-analysis-1"


async def _principal() -> AuthPrincipal:
    return AuthPrincipal(user_id=1, jti="test-jti")


def test_parse_init_should_call_python_application_service() -> None:
    service = AsyncMock()
    app.dependency_overrides[require_principal] = _principal
    app.dependency_overrides[get_project_file_analysis_service] = lambda: service
    try:
        response = TestClient(app).post(
            "/api/v1/projects/10/files/parse/init",
            headers={"X-Trace-Id": _TRACE_ID},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "code": 0,
        "message": "成功",
        "data": None,
        "traceId": _TRACE_ID,
    }
    assert response.headers["X-Trace-Id"] == _TRACE_ID
    service.initialize.assert_awaited_once_with(1, 10)


def test_java_internal_analysis_endpoint_should_be_removed() -> None:
    response = TestClient(app).post(
        "/api/v1/project-files/analyze",
        json=[],
        headers={"X-Trace-Id": _TRACE_ID},
    )

    assert response.status_code == 404
    assert response.headers["X-Trace-Id"] == _TRACE_ID

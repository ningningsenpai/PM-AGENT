"""项目请求模型单元测试。"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.modules.project.schemas import CreateProjectRequest, ProjectResponse


def test_create_project_request_normalizes_name() -> None:
    """验证项目创建请求会去除名称首尾空格。

    @Param project_name: 包含首尾空格的项目名称。
    @Return: 名称已规范化的 CreateProjectRequest。
    """
    request = CreateProjectRequest(project_name="  PM-Agent  ")

    assert request.project_name == "PM-Agent"


def test_create_project_request_rejects_blank_name() -> None:
    """验证项目创建请求拒绝空白名称。

    @Param project_name: 仅包含空格的项目名称。
    @Return: 抛出 ValidationError。
    """
    with pytest.raises(ValidationError):
        CreateProjectRequest(project_name="   ")


def test_project_response_serializes_snowflake_id_as_string() -> None:
    """验证项目响应不会把大整数 ID 作为 JSON 数字输出。"""
    response = ProjectResponse(
        id=9007199254740993,
        project_name="PM-Agent",
        status="active",
        record_status="active",
        created_at=datetime(2026, 9, 2, 10, 0, 0, tzinfo=UTC),
        updated_at=datetime(2026, 9, 2, 10, 0, 0, tzinfo=UTC),
    )

    assert response.model_dump(mode="json")["id"] == "9007199254740993"

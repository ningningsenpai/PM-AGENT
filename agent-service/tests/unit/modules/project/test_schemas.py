"""项目请求模型单元测试。"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.modules.project.schemas import CreateProjectRequest


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

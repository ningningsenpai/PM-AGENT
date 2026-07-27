"""用户请求模型单元测试。"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.modules.user.schemas import (
    ChangePasswordRequest,
    UpdateUserProfileRequest,
)


def test_update_profile_request_normalizes_fields() -> None:
    """验证资料修改请求会规范化用户名和邮箱。

    @Param username: 包含首尾空格的用户名。
    @Param email: 包含首尾空格和大写字符的合法邮箱。
    @Return: 用户名去除空格且邮箱转为小写的 UpdateUserProfileRequest。
    """
    request = UpdateUserProfileRequest(
        username="  Tester  ",
        email="  TESTER@Example.COM  ",
    )

    assert request.username == "Tester"
    assert request.email == "tester@example.com"


@pytest.mark.parametrize(
    ("username", "email"),
    [("   ", "tester@example.com"), ("tester", "invalid")],
)
def test_update_profile_request_rejects_invalid_fields(
    username: str,
    email: str,
) -> None:
    """验证资料修改请求拒绝空用户名或非法邮箱。

    @Param username: 参数化的用户名。
    @Param email: 参数化的邮箱。
    @Return: 抛出 ValidationError。
    """
    with pytest.raises(ValidationError):
        UpdateUserProfileRequest(username=username, email=email)


def test_change_password_request_accepts_matching_passwords() -> None:
    """验证两次新密码一致时请求有效。

    @Param old_password: 当前用户原密码。
    @Param new_password: 满足长度约束的新密码。
    @Param confirm_password: 与新密码一致的确认密码。
    @Return: 校验成功的 ChangePasswordRequest。
    """
    request = ChangePasswordRequest(
        old_password="old-password",
        new_password="new-password",
        confirm_password="new-password",
    )

    assert request.new_password == request.confirm_password


def test_change_password_request_rejects_mismatch() -> None:
    """验证两次新密码不一致时拒绝请求。

    @Param old_password: 当前用户原密码。
    @Param new_password: 满足长度约束的新密码。
    @Param confirm_password: 与新密码不同的确认密码。
    @Return: 抛出 ValidationError。
    """
    with pytest.raises(ValidationError):
        ChangePasswordRequest(
            old_password="old-password",
            new_password="new-password",
            confirm_password="other-password",
        )

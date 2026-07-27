"""认证请求模型单元测试。"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.modules.auth.schemas import LoginRequest, RegisterRequest


def test_login_request_normalizes_email() -> None:
    """验证登录请求会规范化邮箱。

    @Param email: 包含首尾空格和大写字符的合法邮箱。
    @Param password: 满足长度约束的登录密码。
    @Return: 邮箱转换为小写且首尾空格被移除的 LoginRequest。
    """
    request = LoginRequest(email="  USER@Example.COM  ", password="secret")

    assert request.email == "user@example.com"
    assert request.password == "secret"


@pytest.mark.parametrize("email", ["invalid", "user@", "@example.com"])
def test_login_request_rejects_invalid_email(email: str) -> None:
    """验证登录请求拒绝非法邮箱。

    @Param email: 不满足邮箱格式要求的参数化字符串。
    @Param password: 满足长度约束的登录密码。
    @Return: 抛出 ValidationError。
    """
    with pytest.raises(ValidationError):
        LoginRequest(email=email, password="secret")


def test_register_request_normalizes_identity_fields() -> None:
    """验证注册请求会规范化用户名和邮箱。

    @Param username: 包含首尾空格的用户名。
    @Param email: 包含首尾空格和大写字符的合法邮箱。
    @Param password: 满足注册长度约束的密码。
    @Return: 用户名去除首尾空格且邮箱转为小写的 RegisterRequest。
    """
    request = RegisterRequest(
        username="  Tester  ",
        email="  TESTER@Example.COM ",
        password="secret1",
    )

    assert request.username == "Tester"
    assert request.email == "tester@example.com"


@pytest.mark.parametrize(
    ("username", "password"),
    [("   ", "secret1"), ("tester", "12345")],
)
def test_register_request_rejects_invalid_fields(
    username: str,
    password: str,
) -> None:
    """验证注册请求拒绝空用户名或过短密码。

    @Param username: 参数化的用户名。
    @Param email: 固定的合法邮箱。
    @Param password: 参数化的注册密码。
    @Return: 抛出 ValidationError。
    """
    with pytest.raises(ValidationError):
        RegisterRequest(
            username=username,
            email="tester@example.com",
            password=password,
        )

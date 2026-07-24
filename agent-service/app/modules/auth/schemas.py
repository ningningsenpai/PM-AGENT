"""认证请求与响应模型。"""
from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel

from app.modules.user.schemas import UserProfileResponse

_EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class AuthSchema(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class LoginRequest(AuthSchema):
    email: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=64)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not _EMAIL_PATTERN.fullmatch(normalized):
            raise ValueError("邮箱格式不正确")
        return normalized


class RegisterRequest(LoginRequest):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=6, max_length=64)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("用户名不能为空")
        return normalized


class LoginResponse(AuthSchema):
    token_name: str
    token_value: str
    user: UserProfileResponse

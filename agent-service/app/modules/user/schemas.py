"""用户请求与响应模型。"""
from __future__ import annotations

import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic.alias_generators import to_camel

from app.core.identifiers import SnowflakeId

_EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class UserSchema(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


class UserProfileResponse(UserSchema):
    id: SnowflakeId
    username: str
    email: str
    status: str
    last_login_at: datetime | None = None


class UpdateUserProfileRequest(UserSchema):
    username: str = Field(min_length=1, max_length=64)
    email: str = Field(min_length=1, max_length=128)

    @field_validator("username", "email")
    @classmethod
    def strip_value(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("字段不能为空")
        return normalized

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        normalized = value.lower()
        if not _EMAIL_PATTERN.fullmatch(normalized):
            raise ValueError("邮箱格式不正确")
        return normalized


class ChangePasswordRequest(UserSchema):
    old_password: str = Field(min_length=6, max_length=64)
    new_password: str = Field(min_length=6, max_length=64)
    confirm_password: str = Field(min_length=6, max_length=64)

    @model_validator(mode="after")
    def validate_confirmation(self) -> "ChangePasswordRequest":
        if self.new_password != self.confirm_password:
            raise ValueError("两次输入的新密码不一致")
        return self


def to_profile(user) -> UserProfileResponse:
    return UserProfileResponse.model_validate(user)

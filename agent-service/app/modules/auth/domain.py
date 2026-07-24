"""认证领域值对象。"""
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LoginSession:
    token_name: str
    token_value: str

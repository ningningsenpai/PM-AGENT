"""用户领域对象。"""
from enum import StrEnum


class UserStatus(StrEnum):
    ENABLED = "enabled"
    DISABLED = "disabled"

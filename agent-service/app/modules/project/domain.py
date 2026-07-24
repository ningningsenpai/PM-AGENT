"""项目领域状态。"""
from enum import StrEnum


class ProjectStatus(StrEnum):
    INITIALIZING = "initializing"
    ACTIVE = "active"
    INIT_FAILED = "init_failed"

"""项目领域状态。"""
from enum import StrEnum


class ProjectStatus(StrEnum):
    INITIALIZING = "initializing"
    ACTIVE = "active"
    INIT_FAILED = "init_failed"


class ProjectRecordStatus(StrEnum):
    """项目记录是否对业务查询可见。"""

    ACTIVE = "active"
    INACTIVE = "inactive"

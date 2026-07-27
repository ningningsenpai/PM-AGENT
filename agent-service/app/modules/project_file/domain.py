"""项目文件共享业务类型与状态。"""

from enum import StrEnum


class FileBusinessType(StrEnum):
    PROJECT = "project"
    USER = "user"
    SYSTEM = "system"


class ProjectFileStatus(StrEnum):
    UPLOADING = "uploading"
    ACTIVE = "active"
    UPDATING = "updating"
    UPLOAD_FAILED = "upload_failed"
    VERIFY_REQUIRED = "verify_required"
    MISSING = "missing"
    DELETING = "deleting"
    DELETE_FAILED = "delete_failed"


class ProjectFileUploadStatus(StrEnum):
    NOT_UPLOADED = "not_uploaded"
    RETRYING = "retrying"
    SUCCESS = "success"
    FAILED = "failed"

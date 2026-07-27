"""项目对象键生成规则。"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
import re
import unicodedata
from uuid import uuid4

from app.core.config import StorageConfig
from app.core.errors import AppException, ErrorCode

_STORAGE_UUID_PATTERN = re.compile(r"^[0-9a-f]{16}$")


@dataclass(frozen=True, slots=True)
class StorageLocation:
    bucket: str
    object_key: str


class StorageLocationFactory:
    ROOT_PREFIX = "PM-AGENT"

    def __init__(self, config: StorageConfig) -> None:
        self._bucket = config.bucket

    @staticmethod
    def create_storage_uuid() -> str:
        return uuid4().hex[:16]

    def project_prefix(self, user_id: int, project_id: int) -> StorageLocation:
        self._validate_ids(user_id, project_id)
        return StorageLocation(
            self._bucket,
            f"{self.ROOT_PREFIX}/{user_id}/{project_id}/",
        )

    def regular_file(
        self,
        user_id: int,
        project_id: int,
        business_code: str,
        file_name: str,
        storage_uuid: str,
    ) -> StorageLocation:
        if business_code not in {"project", "user"}:
            raise AppException(ErrorCode.SYSTEM_FILE_ACCESS_DENIED)
        storage_name = self.storage_name(file_name, storage_uuid)
        prefix = self.project_prefix(user_id, project_id).object_key
        return StorageLocation(
            self._bucket,
            f"{prefix}{business_code}/{storage_name}",
        )

    def system_file(
        self,
        user_id: int,
        project_id: int,
        relative_path: str,
    ) -> StorageLocation:
        normalized = str(PurePosixPath(relative_path))
        if (
            not normalized
            or normalized.startswith("/")
            or ".." in PurePosixPath(normalized).parts
        ):
            raise AppException(ErrorCode.PARAM_INVALID, "系统文件路径不合法")
        prefix = self.project_prefix(user_id, project_id).object_key
        return StorageLocation(self._bucket, f"{prefix}system/{normalized}")

    @staticmethod
    def storage_name(file_name: str, storage_uuid: str) -> str:
        normalized = unicodedata.normalize("NFC", file_name)
        if (
            not normalized.strip()
            or normalized in {".", ".."}
            or "/" in normalized
            or "\\" in normalized
            or any(ord(character) < 32 for character in normalized)
        ):
            raise AppException(ErrorCode.PARAM_INVALID, "文件名不合法")
        if not _STORAGE_UUID_PATTERN.fullmatch(storage_uuid.lower()):
            raise AppException(ErrorCode.PARAM_INVALID, "文件存储标识必须是16位十六进制字符串")
        dot_index = normalized.rfind(".")
        if dot_index <= 0 or dot_index == len(normalized) - 1:
            return f"{normalized}-{storage_uuid.lower()}"
        return (
            f"{normalized[:dot_index]}-{storage_uuid.lower()}"
            f"{normalized[dot_index:]}"
        )

    def relative_object_path(
        self,
        user_id: int,
        project_id: int,
        object_key: str,
    ) -> str:
        """
        根据固定的 prefix 来从传入的完整对象键判断该路径是否合法
        @Return: storage_name
        """
        prefix = self.project_prefix(user_id, project_id).object_key
        if not object_key.startswith(prefix):
            raise AppException(ErrorCode.PARAM_INVALID, "对象键不属于指定项目")
        return object_key[len(prefix) :]

    def existing_object(
        self,
        user_id: int,
        project_id: int,
        object_key: str,
    ) -> StorageLocation:
        """ relative_object_path -> @Return: storage_name """
        self.relative_object_path(user_id, project_id, object_key)
        return StorageLocation(self._bucket, object_key)

    @staticmethod
    def _validate_ids(user_id: int, project_id: int) -> None:
        if user_id <= 0 or project_id <= 0:
            raise AppException(ErrorCode.PARAM_INVALID, "用户ID和项目ID必须大于0")

"""项目文件存储规则。"""
from __future__ import annotations

from pathlib import PurePosixPath
from urllib.parse import unquote, urlparse
import re
import uuid

from app.core.config import MinIOConfig
from app.project.files.schemas import FileBusiness

__all__ = ["ProjectFileStorage"]

_SAFE_NAME_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")
_SAFE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_ALLOWED_BUSINESS = {business.value for business in FileBusiness}


class ProjectFileStorage:
    """ProjectFileStorage 管理项目文件对象名、URL 和路径解析规则。"""

    def __init__(self, config: MinIOConfig) -> None:
        self._config = config

    @property
    def bucket(self) -> str:
        """返回项目文件使用的默认 bucket。"""
        return self._config.bucket

    def build_object_name(self, user_id: str, project_id: str, business: FileBusiness, file_name: str) -> str:
        """按业务分区构造对象名称。"""
        self._validate_identity(user_id, "userId")
        self._validate_identity(project_id, "projectId")
        safe_name = self.validate_file_name(file_name)
        prefix = f"{uuid.uuid4().hex[:8]}-{safe_name}"
        return f"PM-AGENT/{user_id}/{project_id}/{business.value}/{prefix}"

    def build_url_path(self, object_name: str) -> str:
        """构造对外可用文件路径。"""
        return f"{self._config.public_base_url}/{object_name}"

    def parse_url_path(self, url_path: str) -> tuple[str, str]:
        """把完整 URL 或对象路径归一化为 bucket 和对象名。"""
        raw = unquote(url_path.strip())
        if not raw:
            raise ValueError("文件路径不能为空")
        if raw.startswith("http://") or raw.startswith("https://"):
            parsed = urlparse(raw)
            if parsed.netloc != self._config.public_host:
                raise ValueError("文件路径主机不匹配")
            path = parsed.path.lstrip("/")
        else:
            path = raw.lstrip("/")
            if path.startswith(f"{self._config.bucket}/"):
                path = path[len(self._config.bucket) + 1 :]
        if not path.startswith("PM-AGENT/"):
            raise ValueError("文件路径必须以 PM-AGENT/ 开头")
        if ".." in path or "\\" in path:
            raise ValueError("文件路径不合法")
        parts = path.split("/", 4)
        if len(parts) != 5:
            raise ValueError("文件路径格式不合法")
        self._validate_identity(parts[1], "userId")
        self._validate_identity(parts[2], "projectId")
        if parts[3] not in _ALLOWED_BUSINESS:
            raise ValueError("文件业务类型不合法")
        self.validate_file_name(parts[4])
        return self._config.bucket, path

    def get_path_user_id(self, url_path: str) -> str:
        """从文件路径中解析用户 ID，用于归属校验。"""
        _, object_name = self.parse_url_path(url_path)
        return object_name.split("/", 4)[1]

    def file_name_from_object(self, object_name: str) -> str:
        """从对象名中获取对外展示文件名。"""
        return PurePosixPath(object_name).name

    def validate_file_name(self, file_name: str) -> str:
        """清洗并校验文件名。"""
        normalized = PurePosixPath(file_name).name
        if not normalized or normalized in {".", ".."}:
            raise ValueError("文件名不合法")
        if ".." in normalized or "/" in normalized or "\\" in normalized:
            raise ValueError("文件名不合法")
        if not _SAFE_NAME_PATTERN.fullmatch(normalized):
            raise ValueError("文件名仅允许字母、数字、点、下划线和短横线")
        return normalized

    def _validate_identity(self, value: str, field_name: str) -> None:
        """校验路径身份字段，避免路径注入。"""
        if not _SAFE_ID_PATTERN.fullmatch(value):
            raise ValueError(f"{field_name} 仅允许字母、数字、下划线和短横线，且长度不超过 64")

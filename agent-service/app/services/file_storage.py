"""MinIO 文件存储服务。"""
from __future__ import annotations

from io import BytesIO
from pathlib import PurePosixPath
from urllib.parse import unquote, urlparse
import re
import uuid

from minio import Minio

from app.core.config import MinIOConfig
from app.schemas.files import FileBusiness


_SAFE_NAME_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")
_SAFE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class MinIOFileStorage:
    """封装 MinIO 对象存储的文件读写能力。"""

    def __init__(self, config: MinIOConfig) -> None:
        self._config = config
        self._client = Minio(
            config.endpoint,
            access_key=config.access_key,
            secret_key=config.secret_key,
            secure=config.secure,
        )
        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        """确保默认桶存在。"""
        if not self._client.bucket_exists(self._config.bucket):
            self._client.make_bucket(self._config.bucket)

    def _validate_identity(self, value: str, field_name: str) -> None:
        """校验用户和项目标识只包含安全字符。"""
        if not _SAFE_ID_PATTERN.fullmatch(value):
            raise ValueError(f"{field_name} 仅允许字母、数字、下划线和短横线，且长度不超过 64")

    def _validate_file_name(self, file_name: str) -> str:
        """清洗并校验文件名。"""
        normalized = PurePosixPath(file_name).name
        if not normalized or normalized in {".", ".."}:
            raise ValueError("文件名不合法")
        if ".." in normalized or "/" in normalized or "\\" in normalized:
            raise ValueError("文件名不合法")
        if not _SAFE_NAME_PATTERN.fullmatch(normalized):
            raise ValueError("文件名仅允许字母、数字、点、下划线和短横线")
        return normalized

    def _build_object_name(self, user_id: str, project_id: str, business: FileBusiness, file_name: str) -> str:
        """构造对象名称。"""
        self._validate_identity(user_id, "userId")
        self._validate_identity(project_id, "projectId")
        safe_name = self._validate_file_name(file_name)
        prefix = f"{uuid.uuid4().hex[:8]}-{safe_name}"
        return f"PM-AGENT/{user_id}/{project_id}/{business.value}/{prefix}"

    def _build_url_path(self, object_name: str) -> str:
        """构造对外可用路径。"""
        return f"{self._config.public_base_url}/{object_name}"

    def _parse_url_path(self, url_path: str) -> tuple[str, str]:
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
        if parts[3] not in {business.value for business in FileBusiness}:
            raise ValueError("文件业务类型不合法")
        self._validate_file_name(parts[4])
        return self._config.bucket, path

    def get_path_user_id(self, url_path: str) -> str:
        """从文件路径中解析用户 ID。"""
        _, object_name = self._parse_url_path(url_path)
        return object_name.split("/", 4)[1]

    def upload_file(self, user_id: str, project_id: str, business: FileBusiness, file_name: str, file_bytes: bytes, content_type: str) -> dict:
        """上传文件并返回路径信息。"""
        object_name = self._build_object_name(user_id, project_id, business, file_name)
        self._client.put_object(
            self._config.bucket,
            object_name,
            BytesIO(file_bytes),
            length=len(file_bytes),
            content_type=content_type or "application/octet-stream",
        )
        return {
            "bucket": self._config.bucket,
            "object_name": object_name,
            "file_name": PurePosixPath(object_name).name,
            "url_path": self._build_url_path(object_name),
            "size": len(file_bytes),
            "content_type": content_type or "application/octet-stream",
        }

    def stat_file(self, url_path: str) -> dict:
        """查询文件元信息。"""
        bucket, object_name = self._parse_url_path(url_path)
        stat = self._client.stat_object(bucket, object_name)
        return {
            "bucket": bucket,
            "object_name": object_name,
            "file_name": PurePosixPath(object_name).name,
            "size": stat.size,
            "content_type": stat.content_type or "application/octet-stream",
            "url_path": self._build_url_path(object_name),
        }

    def download_file(self, url_path: str) -> tuple[dict, bytes]:
        """下载文件并返回元信息和内容。"""
        bucket, object_name = self._parse_url_path(url_path)
        response = self._client.get_object(bucket, object_name)
        try:
            content = response.read()
        finally:
            response.close()
            response.release_conn()
        stat = self._client.stat_object(bucket, object_name)
        return (
            {
                "bucket": bucket,
                "object_name": object_name,
                "file_name": PurePosixPath(object_name).name,
                "size": stat.size,
                "content_type": stat.content_type or "application/octet-stream",
                "url_path": self._build_url_path(object_name),
            },
            content,
        )

    def replace_file(self, url_path: str, file_name: str, file_bytes: bytes, content_type: str) -> dict:
        """覆盖更新文件内容。"""
        bucket, object_name = self._parse_url_path(url_path)
        stat = self._client.stat_object(bucket, object_name)
        self._client.put_object(
            bucket,
            object_name,
            BytesIO(file_bytes),
            length=len(file_bytes),
            content_type=content_type or stat.content_type or "application/octet-stream",
        )
        return {
            "bucket": bucket,
            "object_name": object_name,
            "file_name": PurePosixPath(object_name).name,
            "url_path": self._build_url_path(object_name),
            "size": len(file_bytes),
            "content_type": content_type or stat.content_type or "application/octet-stream",
        }

    def delete_file(self, url_path: str) -> dict:
        """删除文件。"""
        bucket, object_name = self._parse_url_path(url_path)
        self._client.remove_object(bucket, object_name)
        return {"deleted": True, "url_path": self._build_url_path(object_name)}

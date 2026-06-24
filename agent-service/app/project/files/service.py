"""项目文件业务服务。"""
from __future__ import annotations

from app.core.config import MinIOConfig
from app.infrastructure.minio_client import MinIOClient
from app.project.files.schemas import FileBusiness
from app.project.files.storage import ProjectFileStorage

__all__ = ["ProjectFileService"]

_DEFAULT_CONTENT_TYPE = "application/octet-stream"


class ProjectFileService:
    """ProjectFileService 编排项目文件业务规则与对象存储操作。"""

    def __init__(self, config: MinIOConfig, client: MinIOClient | None = None) -> None:
        self._config = config
        self._client = client or MinIOClient(config)
        self._storage = ProjectFileStorage(config)

    def upload_file(
        self,
        *,
        user_id: str,
        project_id: str,
        business: FileBusiness,
        file_name: str,
        file_bytes: bytes,
        content_type: str | None,
    ) -> dict:
        """上传项目文件并返回后续操作所需路径信息。"""
        self._validate_file_size(file_bytes)
        object_name = self._storage.build_object_name(user_id, project_id, business, file_name)
        media_type = content_type or _DEFAULT_CONTENT_TYPE
        self._client.put_object(self._storage.bucket, object_name, file_bytes, media_type)
        return self._build_file_result(object_name, len(file_bytes), media_type)

    def stat_file(self, url_path: str, current_user_id: str | None = None) -> dict:
        """查询项目文件元信息，并在有用户上下文时校验归属。"""
        self.validate_path_owner(url_path, current_user_id)
        bucket, object_name = self._storage.parse_url_path(url_path)
        stat = self._client.stat_object(bucket, object_name)
        return self._build_file_result(
            object_name,
            stat.size,
            stat.content_type or _DEFAULT_CONTENT_TYPE,
            bucket=bucket,
        )

    def download_file(self, url_path: str, current_user_id: str | None = None) -> tuple[dict, bytes]:
        """下载项目文件内容，并返回元信息和二进制内容。"""
        self.validate_path_owner(url_path, current_user_id)
        bucket, object_name = self._storage.parse_url_path(url_path)
        content = self._client.get_object_bytes(bucket, object_name)
        stat = self._client.stat_object(bucket, object_name)
        return (
            self._build_file_result(
                object_name,
                stat.size,
                stat.content_type or _DEFAULT_CONTENT_TYPE,
                bucket=bucket,
            ),
            content,
        )

    def replace_file(
        self,
        *,
        url_path: str,
        file_bytes: bytes,
        content_type: str | None,
        current_user_id: str | None = None,
    ) -> dict:
        """覆盖更新项目文件内容，保持原对象路径不变。"""
        self._validate_file_size(file_bytes)
        self.validate_path_owner(url_path, current_user_id)
        bucket, object_name = self._storage.parse_url_path(url_path)
        stat = self._client.stat_object(bucket, object_name)
        media_type = content_type or stat.content_type or _DEFAULT_CONTENT_TYPE
        self._client.put_object(bucket, object_name, file_bytes, media_type)
        return self._build_file_result(object_name, len(file_bytes), media_type, bucket=bucket)

    def delete_file(self, url_path: str, current_user_id: str | None = None) -> dict:
        """删除项目文件。"""
        self.validate_path_owner(url_path, current_user_id)
        bucket, object_name = self._storage.parse_url_path(url_path)
        self._client.remove_object(bucket, object_name)
        return {"deleted": True, "url_path": self._storage.build_url_path(object_name)}

    def validate_path_owner(self, url_path: str, current_user_id: str | None) -> None:
        """校验当前用户与文件路径中的用户归属一致。"""
        if current_user_id is not None and self._storage.get_path_user_id(url_path) != current_user_id:
            raise ValueError("文件路径用户与当前用户不一致")

    def _build_file_result(
        self,
        object_name: str,
        size: int,
        content_type: str,
        *,
        bucket: str | None = None,
    ) -> dict:
        return {
            "bucket": bucket or self._storage.bucket,
            "object_name": object_name,
            "file_name": self._storage.file_name_from_object(object_name),
            "url_path": self._storage.build_url_path(object_name),
            "size": size,
            "content_type": content_type,
        }

    def _validate_file_size(self, file_bytes: bytes) -> None:
        if not file_bytes:
            raise ValueError("文件内容不能为空")
        max_size = self._config.max_file_size_mb * 1024 * 1024
        if len(file_bytes) > max_size:
            raise ValueError("文件大小超出限制")

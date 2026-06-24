"""MinIO 基础设施客户端。"""
from __future__ import annotations

from io import BytesIO

from minio import Minio

from app.core.config import MinIOConfig

__all__ = ["MinIOClient"]


class MinIOClient:
    """MinIOClient 封装对象存储底层读写，不包含项目业务规则。"""

    def __init__(self, config: MinIOConfig) -> None:
        self.config = config
        self._client = Minio(
            config.endpoint,
            access_key=config.access_key,
            secret_key=config.secret_key,
            secure=config.secure,
        )
        self.ensure_bucket()

    def ensure_bucket(self) -> None:
        """确保默认 bucket 存在。"""
        if not self._client.bucket_exists(self.config.bucket):
            self._client.make_bucket(self.config.bucket)

    def put_object(self, bucket: str, object_name: str, data: bytes, content_type: str) -> None:
        """上传对象内容。"""
        self._client.put_object(
            bucket,
            object_name,
            BytesIO(data),
            length=len(data),
            content_type=content_type,
        )

    def stat_object(self, bucket: str, object_name: str):
        """查询对象元信息。"""
        return self._client.stat_object(bucket, object_name)

    def get_object_bytes(self, bucket: str, object_name: str) -> bytes:
        """读取对象内容并释放底层连接。"""
        response = self._client.get_object(bucket, object_name)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    def remove_object(self, bucket: str, object_name: str) -> None:
        """删除对象。"""
        self._client.remove_object(bucket, object_name)

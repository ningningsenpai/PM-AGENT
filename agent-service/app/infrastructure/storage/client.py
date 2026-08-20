"""MinIO 对象存储客户端。"""

from __future__ import annotations

from datetime import timedelta
from functools import lru_cache
from io import BytesIO

from minio import Minio
from minio.error import S3Error

from app.core.config import get_settings
from app.core.errors import AppException, ErrorCode
from app.infrastructure.storage.location import StorageLocation


class ObjectStorage:
    """封装 MinIO 客户端，并提供对象字节读写和生命周期操作。"""

    def __init__(self, client: Minio, read_url_expiry_seconds: int) -> None:
        self._client = client
        self._read_url_expiry_seconds = read_url_expiry_seconds

    def put_bytes(
        self,
        location: StorageLocation,
        content: bytes,
        content_type: str,
    ) -> None:
        """将字节内容写入指定对象位置。"""
        try:
            self._ensure_bucket(location.bucket)
            self._client.put_object(
                location.bucket,
                location.object_key,
                BytesIO(content),
                len(content),
                content_type=content_type,
            )
        except AppException:
            raise
        except Exception as exception:
            raise AppException(ErrorCode.FILE_STORAGE_ERROR) from exception

    def read_bytes(self, location: StorageLocation) -> bytes:
        """从对象存储读取源文件原始字节，不执行内容提取或语义分析。"""
        response = None
        try:
            response = self._client.get_object(location.bucket, location.object_key)
            return response.read()
        except Exception as exception:
            raise AppException(ErrorCode.FILE_STORAGE_ERROR) from exception
        finally:
            if response is not None:
                response.close()
                response.release_conn()

    def exists(self, location: StorageLocation) -> bool:
        """根据 bucket 和 object_key，判断对象是否存在，同时区分不存在与存储服务异常。"""
        try:
            self._client.stat_object(location.bucket, location.object_key)
            return True
        except S3Error as exception:
            if exception.code in {"NoSuchBucket", "NoSuchKey", "NoSuchObject"}:
                return False
            raise AppException(ErrorCode.FILE_STORAGE_ERROR) from exception
        except Exception as exception:
            raise AppException(ErrorCode.FILE_STORAGE_ERROR) from exception

    def copy(self, source: StorageLocation, target: StorageLocation) -> None:
        """复制对象存储中的文件"""
        from minio.commonconfig import CopySource

        try:
            self._ensure_bucket(target.bucket)
            self._client.copy_object(
                target.bucket,
                target.object_key,
                CopySource(source.bucket, source.object_key),
            )
        except Exception as exception:
            raise AppException(ErrorCode.FILE_STORAGE_ERROR) from exception

    def remove(self, location: StorageLocation) -> None:
        """删除对象存储中的文件"""
        try:
            self._client.remove_object(location.bucket, location.object_key)
        except Exception as exception:
            raise AppException(ErrorCode.FILE_STORAGE_ERROR) from exception

    def remove_prefix(self, location: StorageLocation) -> None:
        """删除对象存储中的文件前缀"""
        try:
            if not self._client.bucket_exists(location.bucket):
                return
            for item in self._client.list_objects(
                location.bucket,
                prefix=location.object_key,
                recursive=True,
            ):
                self._client.remove_object(location.bucket, item.object_name)
        except Exception as exception:
            raise AppException(ErrorCode.FILE_STORAGE_ERROR) from exception

    def list_prefix(self, location: StorageLocation) -> list[StorageLocation]:
        """列出指定前缀下的全部对象位置，不读取对象内容。"""
        try:
            if not self._client.bucket_exists(location.bucket):
                return []
            return [
                StorageLocation(location.bucket, item.object_name)
                for item in self._client.list_objects(
                    location.bucket,
                    prefix=location.object_key,
                    recursive=True,
                )
            ]
        except Exception as exception:
            raise AppException(ErrorCode.FILE_STORAGE_ERROR) from exception

    def presigned_get(self, location: StorageLocation) -> str:
        """生成预签名URL，用于临时访问对象存储中的文件"""
        try:
            return self._client.presigned_get_object(
                location.bucket,
                location.object_key,
                expires=timedelta(seconds=self._read_url_expiry_seconds),
            )
        except Exception as exception:
            raise AppException(ErrorCode.FILE_STORAGE_ERROR) from exception

    def _ensure_bucket(self, bucket: str) -> None:
        """确保对象存储中的 bucket 存在"""
        if not self._client.bucket_exists(bucket):
            self._client.make_bucket(bucket)


@lru_cache
def get_object_storage() -> ObjectStorage:
    config = get_settings().storage
    client = Minio(
        config.endpoint,
        access_key=config.access_key,
        secret_key=config.secret_key,
        secure=config.secure,
    )
    return ObjectStorage(client, config.read_url_expiry_seconds)

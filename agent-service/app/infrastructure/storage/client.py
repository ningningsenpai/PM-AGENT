"""MinIO 对象存储客户端。"""
from __future__ import annotations

from datetime import timedelta
from functools import lru_cache
from io import BytesIO

from minio import Minio

from app.core.config import get_settings
from app.core.errors import AppException, ErrorCode
from app.infrastructure.storage.location import StorageLocation


class ObjectStorage:
    def __init__(self, client: Minio, read_url_expiry_seconds: int) -> None:
        self._client = client
        self._read_url_expiry_seconds = read_url_expiry_seconds

    def put_bytes(
        self,
        location: StorageLocation,
        content: bytes,
        content_type: str,
    ) -> None:
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

    def get_bytes(self, location: StorageLocation) -> bytes:
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

    def copy(self, source: StorageLocation, target: StorageLocation) -> None:
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
        try:
            self._client.remove_object(location.bucket, location.object_key)
        except Exception as exception:
            raise AppException(ErrorCode.FILE_STORAGE_ERROR) from exception

    def remove_prefix(self, location: StorageLocation) -> None:
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

    def presigned_get(self, location: StorageLocation) -> str:
        try:
            return self._client.presigned_get_object(
                location.bucket,
                location.object_key,
                expires=timedelta(seconds=self._read_url_expiry_seconds),
            )
        except Exception as exception:
            raise AppException(ErrorCode.FILE_STORAGE_ERROR) from exception

    def _ensure_bucket(self, bucket: str) -> None:
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

"""内存对象存储模拟，保留条件写入和失败恢复语义。"""

import hashlib
from threading import RLock

from app.core.errors import AppException, ErrorCode


class MemoryStorage:
    def __init__(self):
        self.data = {}
        self.lock = RLock()
        self.fail_suffix = None
        self.lose_ack = False

    def read_versioned(self, location):
        with self.lock:
            content = self.data.get((location.bucket, location.object_key))
            return (
                (content, hashlib.md5(content).hexdigest())
                if content is not None
                else None
            )

    def compare_and_put(self, location, content, etag):
        with self.lock:
            if self.fail_suffix and location.object_key.endswith(self.fail_suffix):
                raise AppException(ErrorCode.FILE_STORAGE_ERROR, "模拟对象写入失败")
            old = self.read_versioned(location)
            if (old[1] if old else None) != etag:
                raise AppException(ErrorCode.RESOURCE_CONFLICT, "模拟云端版本冲突")
            self.data[(location.bucket, location.object_key)] = content
            if self.lose_ack and location.object_key.endswith("context/manifest.json"):
                self.lose_ack = False
                raise AppException(ErrorCode.FILE_STORAGE_ERROR, "模拟写入后响应丢失")
            return hashlib.md5(content).hexdigest()

    def exists(self, location):
        return (location.bucket, location.object_key) in self.data

    def read_bytes(self, location):
        return self.data[(location.bucket, location.object_key)]

    def put_bytes(self, location, content, content_type):
        self.data[(location.bucket, location.object_key)] = content

    def remove(self, location):
        self.data.pop((location.bucket, location.object_key), None)

    def list_prefix(self, location):
        from app.infrastructure.storage import StorageLocation

        return [
            StorageLocation(bucket, key)
            for bucket, key in self.data
            if bucket == location.bucket and key.startswith(location.object_key)
        ]

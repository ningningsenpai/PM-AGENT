"""MinIO 对象存储适配。"""
from .client import ObjectStorage, get_object_storage
from .location import StorageLocation, StorageLocationFactory

__all__ = [
    "ObjectStorage",
    "StorageLocation",
    "StorageLocationFactory",
    "get_object_storage",
]

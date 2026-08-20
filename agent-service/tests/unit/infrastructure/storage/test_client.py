"""MinIO 对象存储客户端单元测试。"""

from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock

from app.core.errors import AppException
from app.infrastructure.storage import ObjectStorage, StorageLocation


class ObjectStorageListPrefixTest(TestCase):
    def test_list_prefix_returns_locations_in_same_bucket(self) -> None:
        client = Mock()
        client.bucket_exists.return_value = True
        client.list_objects.return_value = [
            SimpleNamespace(object_name="root/a.json"),
            SimpleNamespace(object_name="root/nested/b.json"),
        ]
        storage = ObjectStorage(client, 300)

        result = storage.list_prefix(StorageLocation("bucket", "root/"))

        self.assertEqual(
            [
                StorageLocation("bucket", "root/a.json"),
                StorageLocation("bucket", "root/nested/b.json"),
            ],
            result,
        )
        client.list_objects.assert_called_once_with(
            "bucket",
            prefix="root/",
            recursive=True,
        )

    def test_list_prefix_wraps_storage_error(self) -> None:
        client = Mock()
        client.bucket_exists.side_effect = RuntimeError("连接失败")
        storage = ObjectStorage(client, 300)

        with self.assertRaises(AppException):
            storage.list_prefix(StorageLocation("bucket", "root/"))

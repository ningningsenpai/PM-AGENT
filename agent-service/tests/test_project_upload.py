"""项目文件接口单元测试 —— 覆盖上传、查询、下载、覆盖更新和删除。"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

import app.api.v1.project_files as _pf
from app.api.v1.project_files import get_project_file_service
from app.main import app

TEST_USER_ID = "001"
TEST_PROJECT_ID = "0001"
URL_PATH = f"http://localhost:9000/pm-agent/PM-AGENT/{TEST_USER_ID}/{TEST_PROJECT_ID}/project/abc-README.md"


class _MockS3Error(Exception):
    """模拟 MinIO S3Error，替换 project_files 模块中的 S3Error 引用后使 isinstance 检查通过。"""

    def __init__(self, *args: object) -> None:
        super().__init__(*args)
        self.message = args[0] if args else ""


def _headers() -> dict[str, str]:
    return {}


class _BaseFileTest(unittest.TestCase):
    """文件接口测试基类，统一管理 mock service 与 TestClient。"""

    def setUp(self) -> None:
        self.service_mock = MagicMock()
        app.dependency_overrides[get_project_file_service] = lambda: self.service_mock
        self.client = TestClient(app)
        # 保存原始的 S3Error 并替换为 Mock，使 isinstance 检查可通过
        self._orig_s3_error = _pf.S3Error
        _pf.S3Error = _MockS3Error

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        _pf.S3Error = self._orig_s3_error


# ---------- 上传 ----------

class TestFileUpload(_BaseFileTest):

    def test_upload_success(self) -> None:
        self.service_mock.upload_file.return_value = {
            "bucket": "pm-agent",
            "object_name": f"PM-AGENT/{TEST_USER_ID}/{TEST_PROJECT_ID}/project/abc-README.md",
            "file_name": "README.md",
            "url_path": URL_PATH,
            "size": 100,
            "content_type": "text/markdown",
        }
        response = self.client.post(
            "/api/v1/project/files",
            headers=_headers(),
            data={"projectId": TEST_PROJECT_ID, "business": "project", "userId": TEST_USER_ID},
            files={"file": ("README.md", b"# Hello", "text/markdown")},
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["file_name"], "README.md")
        self.assertEqual(body["size"], 100)
        self.assertIn("url_path", body)

    def test_upload_empty_file_returns_400(self) -> None:
        self.service_mock.upload_file.side_effect = ValueError("文件内容不能为空")
        response = self.client.post(
            "/api/v1/project/files",
            headers=_headers(),
            data={"projectId": TEST_PROJECT_ID, "business": "project", "userId": TEST_USER_ID},
            files={"file": ("empty.txt", b"", "text/plain")},
        )
        self.assertEqual(response.status_code, 400)

    def test_upload_service_value_error_returns_400(self) -> None:
        self.service_mock.upload_file.side_effect = ValueError("文件路径不合法")
        response = self.client.post(
            "/api/v1/project/files",
            headers=_headers(),
            data={"projectId": TEST_PROJECT_ID, "business": "project", "userId": TEST_USER_ID},
            files={"file": ("bad.txt", b"x", "text/plain")},
        )
        self.assertEqual(response.status_code, 400)

    def test_upload_s3_error_returns_502(self) -> None:
        self.service_mock.upload_file.side_effect = _MockS3Error("MinIO 内部错误")
        response = self.client.post(
            "/api/v1/project/files",
            headers=_headers(),
            data={"projectId": TEST_PROJECT_ID, "business": "project", "userId": TEST_USER_ID},
            files={"file": ("test.txt", b"content", "text/plain")},
        )
        self.assertEqual(response.status_code, 502)


# ---------- 查询元信息 ----------

class TestGetFile(_BaseFileTest):

    def test_get_file_info_success(self) -> None:
        self.service_mock.stat_file.return_value = {
            "bucket": "pm-agent",
            "object_name": "PM-AGENT/u1/p1/project/abc-README.md",
            "file_name": "README.md",
            "url_path": URL_PATH,
            "size": 200,
            "content_type": "text/markdown",
        }
        response = self.client.get(
            "/api/v1/project/files",
            headers=_headers(),
            params={"urlPath": URL_PATH},
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["file_name"], "README.md")
        self.assertEqual(body["size"], 200)

    def test_get_file_ownership_mismatch_returns_400(self) -> None:
        self.service_mock.stat_file.side_effect = ValueError("文件路径用户与当前用户不一致")
        response = self.client.get(
            "/api/v1/project/files",
            headers=_headers(),
            params={"urlPath": URL_PATH},
        )
        self.assertEqual(response.status_code, 400)

    def test_get_file_missing_url_path_returns_422(self) -> None:
        response = self.client.get(
            "/api/v1/project/files",
            headers=_headers(),
        )
        self.assertEqual(response.status_code, 422)


# ---------- 下载 ----------

class TestDownloadFile(_BaseFileTest):

    def test_download_success(self) -> None:
        self.service_mock.download_file.return_value = (
            {"file_name": "README.md", "content_type": "text/markdown"},
            b"# Hello World",
        )
        response = self.client.get(
            "/api/v1/project/files/download",
            headers=_headers(),
            params={"urlPath": URL_PATH},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"# Hello World")
        self.assertIn("attachment", response.headers["content-disposition"])

    def test_download_value_error_returns_400(self) -> None:
        self.service_mock.download_file.side_effect = ValueError("文件路径不合法")
        response = self.client.get(
            "/api/v1/project/files/download",
            headers=_headers(),
            params={"urlPath": "invalid-path"},
        )
        self.assertEqual(response.status_code, 400)


# ---------- 覆盖更新 ----------

class TestReplaceFile(_BaseFileTest):

    def test_replace_success(self) -> None:
        self.service_mock.replace_file.return_value = {
            "bucket": "pm-agent",
            "object_name": "PM-AGENT/u1/p1/project/abc-README.md",
            "file_name": "README.md",
            "url_path": URL_PATH,
            "size": 300,
            "content_type": "text/markdown",
        }
        response = self.client.put(
            "/api/v1/project/files",
            headers=_headers(),
            params={"urlPath": URL_PATH},
            files={"file": ("README.md", b"updated content", "text/markdown")},
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["size"], 300)
        self.assertEqual(body["file_name"], "README.md")

    def test_replace_ownership_mismatch_returns_400(self) -> None:
        self.service_mock.replace_file.side_effect = ValueError("文件路径用户与当前用户不一致")
        response = self.client.put(
            "/api/v1/project/files",
            headers=_headers(),
            params={"urlPath": URL_PATH},
            files={"file": ("README.md", b"updated content", "text/markdown")},
        )
        self.assertEqual(response.status_code, 400)


# ---------- 删除 ----------

class TestDeleteFile(_BaseFileTest):

    def test_delete_success(self) -> None:
        self.service_mock.delete_file.return_value = {
            "deleted": True,
            "url_path": URL_PATH,
        }
        response = self.client.delete(
            "/api/v1/project/files",
            headers=_headers(),
            params={"urlPath": URL_PATH},
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["deleted"])

    def test_delete_ownership_mismatch_returns_400(self) -> None:
        self.service_mock.delete_file.side_effect = ValueError("文件路径用户与当前用户不一致")
        response = self.client.delete(
            "/api/v1/project/files",
            headers=_headers(),
            params={"urlPath": URL_PATH},
        )
        self.assertEqual(response.status_code, 400)

    def test_delete_service_value_error_returns_400(self) -> None:
        self.service_mock.delete_file.side_effect = ValueError("文件路径不合法")
        response = self.client.delete(
            "/api/v1/project/files",
            headers=_headers(),
            params={"urlPath": "bad-path"},
        )
        self.assertEqual(response.status_code, 400)

    def test_delete_s3_error_returns_502(self) -> None:
        self.service_mock.delete_file.side_effect = _MockS3Error("对象不存在")
        response = self.client.delete(
            "/api/v1/project/files",
            headers=_headers(),
            params={"urlPath": URL_PATH},
        )
        self.assertEqual(response.status_code, 502)


if __name__ == "__main__":
    unittest.main()

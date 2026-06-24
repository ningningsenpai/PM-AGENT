import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

import requests


class ProjectUploadApiTest(unittest.TestCase):
    """测试项目文件上传接口的完整增删改查链路。"""

    BASE_URL = "http://127.0.0.1:8000"
    USER_ID = "u1"
    PROJECT_ID = "p1"
    BUSINESS = "project"
    TIMEOUT_SECONDS = 30

    def test_project_file_crud_flow(self) -> None:
        """验证文件上传、查询、下载、覆盖更新和删除。"""
        url_path: str | None = None

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            test_file = temp_path / "README.md"
            update_file = temp_path / "update-demo.txt"
            downloaded_file = temp_path / "downloaded-test-file"

            test_file.write_text("original content", encoding="utf-8")
            update_file.write_text("new content", encoding="utf-8")

            try:
                uploaded = self._upload_file(test_file)
                url_path = uploaded["url_path"]

                file_info = self._get_file_info(url_path)
                self.assertEqual(file_info["url_path"], url_path)
                self.assertGreater(file_info["size"], 0)

                downloaded_file.write_bytes(self._download_file(url_path))
                self.assertEqual(downloaded_file.read_text(encoding="utf-8"), "original content")

                updated = self._replace_file(url_path, update_file)
                self.assertEqual(updated["url_path"], url_path)

                updated_content = self._download_file(url_path).decode("utf-8")
                self.assertEqual(updated_content, "new content")

                deleted = self._delete_file(url_path)
                self.assertTrue(deleted["deleted"])
            finally:
                if url_path:
                    self._delete_file_if_exists(url_path)

    def _upload_file(self, file_path: Path) -> dict:
        with file_path.open("rb") as file:
            response = requests.post(
                f"{self.BASE_URL}/api/v1/files",
                headers={
                    "X-User-Id": self.USER_ID,
                    "X-Idempotency-Key": f"upload-{uuid4().hex}",
                },
                data={
                    "userId": self.USER_ID,
                    "projectId": self.PROJECT_ID,
                    "business": self.BUSINESS,
                },
                files={"file": (file_path.name, file, "text/markdown")},
                timeout=self.TIMEOUT_SECONDS,
            )
        response.raise_for_status()
        return response.json()

    def _get_file_info(self, url_path: str) -> dict:
        response = requests.get(
            f"{self.BASE_URL}/api/v1/files",
            headers={"X-User-Id": self.USER_ID},
            params={"urlPath": url_path},
            timeout=self.TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return response.json()

    def _download_file(self, url_path: str) -> bytes:
        response = requests.get(
            f"{self.BASE_URL}/api/v1/files/download",
            headers={"X-User-Id": self.USER_ID},
            params={"urlPath": url_path},
            timeout=self.TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return response.content

    def _replace_file(self, url_path: str, file_path: Path) -> dict:
        with file_path.open("rb") as file:
            response = requests.put(
                f"{self.BASE_URL}/api/v1/files",
                headers={
                    "X-User-Id": self.USER_ID,
                    "X-Idempotency-Key": f"update-{uuid4().hex}",
                },
                params={"urlPath": url_path},
                files={"file": (file_path.name, file, "text/plain")},
                timeout=self.TIMEOUT_SECONDS,
            )
        response.raise_for_status()
        return response.json()

    def _delete_file(self, url_path: str) -> dict:
        response = requests.delete(
            f"{self.BASE_URL}/api/v1/files",
            headers={
                "X-User-Id": self.USER_ID,
                "X-Idempotency-Key": f"delete-{uuid4().hex}",
            },
            params={"urlPath": url_path},
            timeout=self.TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return response.json()

    def _delete_file_if_exists(self, url_path: str) -> None:
        try:
            self._delete_file(url_path)
        except requests.HTTPError:
            pass


if __name__ == "__main__":
    unittest.main()

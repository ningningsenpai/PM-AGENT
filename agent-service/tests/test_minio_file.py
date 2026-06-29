import mimetypes
from pathlib import Path
import unittest

from fastapi.testclient import TestClient

from app.main import app
from app.project.files import FileBusiness


class MyTestCase(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.file_path = Path("D:/Code/ning/PM-AGENT/agent-service/file-tree-test/rag/build_qdrant_index.py")
        self.project_id = "001"
        self.user_id = "001"
        self.business = FileBusiness.PROJECT.value

        if not self.file_path.is_file():
            raise FileNotFoundError(f"文件不存在：{self.file_path}")

        self.content_type = mimetypes.guess_type(self.file_path.name)[0] or "application/octet-stream"

    def test_minio_file_upload(self):
        response = self._upload_file()

        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["content_type"], self.content_type)
        self.assertGreater(body["size"], 0)
        self.assertIn("url_path", body)
        print(body)

    def test_minio_file_view(self):
        upload_body = self._upload_file().json()

        response = self.client.get(
            "/api/v1/minio/files/view",
            params={
                "urlPath": upload_body["url_path"],
                "currentUserId": self.user_id,
            },
        )

        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        print(body)
        self.assertEqual(body["url_path"], upload_body["url_path"])
        self.assertEqual(body["file_name"], upload_body["file_name"])
        self.assertEqual(body["size"], upload_body["size"])
        self.assertEqual(body["content_type"], upload_body["content_type"])
        print(body)

    def test_minio_file_download(self):
        upload_body = self._upload_file().json()
        expected_content = self.file_path.read_bytes()

        response = self.client.get(
            "/api/v1/minio/files/download",
            params={
                "urlPath": upload_body["url_path"],
                "currentUserId": self.user_id,
            },
        )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.content, expected_content)
        self.assertEqual(response.headers["content-type"].split(";")[0], self.content_type)
        self.assertIn("attachment", response.headers["content-disposition"])

    def test_minio_file_update(self):
        upload_body = self._upload_file().json()
        updated_content = b"print('updated by test_minio_file')\n"
        updated_file_name = "updated_build_qdrant_index.py"
        updated_content_type = "text/x-python"

        response = self.client.put(
            "/api/v1/minio/files/update",
            params={"urlPath": upload_body["url_path"]},
            data={"currentUserId": self.user_id},
            files={"file": (updated_file_name, updated_content, updated_content_type)},
        )

        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["url_path"], upload_body["url_path"])
        self.assertEqual(body["file_name"], upload_body["file_name"])
        self.assertEqual(body["size"], len(updated_content))
        self.assertEqual(body["content_type"], updated_content_type)
        print(body)

    def test_minio_file_delete(self):
        upload_body = self._upload_file().json()

        response = self.client.delete(
            "/api/v1/minio/files/delete",
            params={
                "urlPath": upload_body["url_path"],
                "currentUserId": self.user_id,
            },
        )

        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertTrue(body["deleted"])
        self.assertEqual(body["url_path"], upload_body["url_path"])
        print(body)

    def _upload_file(self):
        with self.file_path.open("rb") as file:
            return self.client.post(
                "/api/v1/minio/files/upload",
                data={
                    "projectId": self.project_id,
                    "business": self.business,
                    "userId": self.user_id,
                },
                files={"file": (self.file_path.name, file, self.content_type)},
            )


if __name__ == "__main__":
    unittest.main()

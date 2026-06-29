import unittest

from fastapi.testclient import TestClient

from app.main import app


class MyTestCase(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_build_project_file_tree(self):
        response = self.client.post(
            "/api/v1/project/files/build",
            json={
                "root_path": "D:/Code/ning/PM-AGENT/agent-service/file-tree-test",
                "output_dir": "D:/Code/ning/PM-AGENT/agent-service/tests",
                "user_id": "001",
                "project_id": "001",
                "business": "project",
            },
        )

        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertIsInstance(body, list)
        if body:
            first_item = body[0]
            self.assertIn("original_file_name", first_item)
            self.assertIn("original_path", first_item)
            self.assertIn("_is_delete", first_item)
            self.assertIn("business", first_item)
            self.assertIn("file_info", first_item)
        print(body)

    def test_update_project_file_tree(self):
        response = self.client.post(
            "/api/v1/project/files/update-tree",
            json={
                "root_path": "D:/Code/ning/PM-AGENT/agent-service/file-tree-test",
                "output_dir": "D:/Code/ning/PM-AGENT/agent-service/tests",
                "user_id": "001",
                "project_id": "001",
                "business": "project",
            },
        )

        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        print(body)
        self.assertIsInstance(body, list)
        if body:
            first_item = body[0]
            self.assertIn("original_file_name", first_item)
            self.assertIn("original_path", first_item)
            self.assertIn("_is_delete", first_item)
            self.assertIn("business", first_item)
            self.assertIn("file_info", first_item)
        print(body)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
from pathlib import Path
from unittest import TestCase

from app.project.context import JsonFileConverter


class JsonFileConverterTest(TestCase):
    def setUp(self) -> None:
        self.converter = JsonFileConverter()

    def test_to_memory_file_should_return_utf8_json(self) -> None:
        memory_file = self.converter.to_memory_file({"name": "项目文件", "count": 2})

        self.assertEqual(0, memory_file.tell())
        self.assertEqual(
            {"name": "项目文件", "count": 2},
            json.loads(memory_file.read().decode("utf-8")),
        )

    def test_to_file_should_create_parent_directory_and_write_json(self) -> None:
        target_path = Path(__file__).with_name(".json-file-converter-test.json")
        self.addCleanup(target_path.unlink, missing_ok=True)

        result_path = self.converter.to_file('{"status": "完成"}', target_path)

        self.assertEqual(target_path, result_path)
        self.assertEqual(
            {"status": "完成"},
            json.loads(target_path.read_text(encoding="utf-8")),
        )

    def test_invalid_json_string_should_be_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "JSON 字符串格式无效"):
            self.converter.to_memory_file('{"name":}')

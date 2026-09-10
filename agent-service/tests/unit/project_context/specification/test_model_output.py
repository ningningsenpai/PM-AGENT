"""规范模型字段名纠正与严格持久化边界测试。"""

from __future__ import annotations

import json
from unittest import TestCase

from pydantic import ValidationError

from app.project_context.specification.model_output import normalize_specification_json
from app.project_context.specification.schemas import ProjectSpecificationDocument


class SpecificationModelOutputTest(TestCase):
    def test_top_level_json_object_metadata_is_removed(self):
        payload = json.loads(ProjectSpecificationDocument.empty(10).model_dump_json())
        payload["type"] = "json_object"
        raw = json.dumps(payload, ensure_ascii=False)

        with self.assertRaises(ValidationError):
            ProjectSpecificationDocument.model_validate_json(raw)
        with self.assertLogs(
            "app.project_context.specification.model_output", level="WARNING"
        ) as logs:
            normalized = normalize_specification_json(raw)

        saved = ProjectSpecificationDocument.model_validate_json(normalized)
        self.assertEqual(10, saved.project_id)
        self.assertNotIn("type", json.loads(normalized))
        self.assertIn("type:json_object->removed", "\n".join(logs.output))

    def test_only_rule_body_field_is_renamed_in_each_category(self):
        now = "2026-09-08T17:00:04"
        for field, expected, alias in (
            ("development_approach", "rule", "constraint"),
            ("coding_rules", "rule", "constraint"),
            ("document_rules", "rule", "constraint"),
            ("risk_rules", "rule", "constraint"),
            ("technical_constraints", "constraint", "rule"),
        ):
            with self.subTest(field=field):
                rule = {
                    "id": "stable-rule",
                    alias: "需要保留的原始正文",
                    "scope": "all",
                    "status": "active",
                    "confidence": "high",
                    "created_at": now,
                    "updated_at": now,
                    "source_refs": [
                        {
                            "type": "doc",
                            "path": "docs/规范.md",
                            "file_id": 31,
                            "content_hash": "hash",
                            "detail_ref": "system/detail.json",
                        }
                    ],
                    "previous_versions": [{"constraint": "保留原有历史"}],
                }
                payload = {
                    "project_id": "90727272893382656",
                    "updated_at": now,
                    "project_specification": {field: [rule]},
                }
                raw = json.dumps(payload, ensure_ascii=False)
                with self.assertRaises(ValidationError):
                    ProjectSpecificationDocument.model_validate_json(raw)
                with self.assertLogs(
                    "app.project_context.specification.model_output", level="WARNING"
                ) as logs:
                    normalized = normalize_specification_json(raw)
                saved = ProjectSpecificationDocument.model_validate_json(normalized)
                canonical = json.loads(normalized)["project_specification"][field][0]
                self.assertEqual(
                    {
                        **{key: value for key, value in rule.items() if key != alias},
                        expected: rule[alias],
                    },
                    canonical,
                )
                self.assertEqual(90727272893382656, saved.project_id)
                self.assertIn(field, "\n".join(logs.output))
                self.assertNotIn("需要保留的原始正文", "\n".join(logs.output))
                self.assertNotIn("docs/规范.md", "\n".join(logs.output))

    def test_invalid_structure_or_unrecognized_fields_are_not_repaired(self):
        for content in (
            '{"project_specification":',
            "[]",
            "null",
            '{"project_specification": []}',
            '{"project_specification": {"coding_rules": {"constraint": "正文"}}}',
            '{"project_specification": {"coding_rules": [null, 1]}}',
            '{"project_specification": {"coding_rules": [{"constraint": ["正文"]}]}}',
            '{"project_specification": {"coding_rules": [{"text": "正文"}]}}',
            '{"project_specification": {"coding_rules": [{"rule": "正文", "constraint": "正文"}]}}',
            '{"project_specification": {"coding_rules": [{"rule": null, "constraint": "正文"}]}}',
            '{"type": "other", "project_specification": {}}',
            '{"unexpected": true, "project_specification": {}}',
        ):
            with self.subTest(content=content):
                self.assertEqual(content, normalize_specification_json(content))

    def test_valid_canonical_document_is_unchanged(self):
        content = ProjectSpecificationDocument.empty(10).model_dump_json()
        self.assertEqual(content, normalize_specification_json(content))

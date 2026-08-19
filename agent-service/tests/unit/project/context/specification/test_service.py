"""项目规范构建服务单元测试。"""

from __future__ import annotations

from datetime import datetime
import json
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock

from app.infrastructure.storage import StorageLocationFactory
from app.project.context.specification.schemas import (
    DevelopmentApproachRule,
    ProjectSpecificationBody,
    ProjectSpecificationDocument,
    SpecificationSourceRef,
    merge_specifications,
)
from app.project.context.detail_analysis.schemas import FileRuleCandidate
from app.project.context.specification.service import ProjectSpecificationService
from tests.unit.modules.project_file.analysis.factories import file_detail
from tests.unit.modules.project_file.factories import (
    project,
    project_file,
    storage_config,
)


def _document(
    rule_text: str,
    *,
    include_rule: bool = True,
    source_refs: list[SpecificationSourceRef] | None = None,
):
    now = datetime(2026, 8, 3, 10, 0, 0)
    rules = []
    if include_rule:
        rules.append(
            DevelopmentApproachRule(
                id="development-approach-1",
                rule=rule_text,
                scope="global",
                status="active",
                confidence="high",
                source_refs=source_refs or [],
                created_at=now,
                updated_at=now,
            )
        )
    return ProjectSpecificationDocument(
        project_id=10,
        updated_at=now,
        project_specification=ProjectSpecificationBody(
            development_approach=rules,
        ),
    )


class ProjectSpecificationServiceTest(IsolatedAsyncioTestCase):
    def test_merge_preserves_omitted_rules_and_updates_same_id(self) -> None:
        existing = _document("旧规则")
        updated = merge_specifications(existing, _document("新规则"))
        omitted = merge_specifications(
            existing,
            _document("", include_rule=False),
        )

        self.assertEqual(
            "新规则",
            updated.project_specification.development_approach[0].rule,
        )
        self.assertEqual(
            "旧规则",
            omitted.project_specification.development_approach[0].rule,
        )

    async def test_refresh_generates_and_stores_specification(self) -> None:
        storage = Mock()
        storage.exists.side_effect = [False, True]
        generator = SimpleNamespace(
            generate=AsyncMock(
                return_value=_document(
                    "新规则",
                    source_refs=[
                        SpecificationSourceRef(type="doc", path="docs/README.md")
                    ],
                )
            )
        )
        service = ProjectSpecificationService(
            storage,
            StorageLocationFactory(storage_config()),
            generator,
        )
        file = project_file()
        file.analysis_version = "file-detail-v1"
        file.summary = "项目采用 FastAPI 单体架构"
        file.importance = "high"
        file.file_type = "doc"
        file.detail_ref = "system/file_details/README-a1b2c3d4e5f67890.json"
        detail = file_detail(file).model_copy(
            update={
                "rule_candidates": [
                    FileRuleCandidate(
                        category="technical_constraint",
                        text="后端使用 FastAPI",
                        confidence="high",
                        evidence=["文档明确声明后端技术栈"],
                    )
                ]
            }
        )
        storage.get_bytes.return_value = detail.model_dump_json().encode()

        status = await service.refresh(project(), [file])

        self.assertEqual("updated", status)
        generator.generate.assert_awaited_once()
        storage.put_bytes.assert_called_once()
        location, content, content_type = storage.put_bytes.call_args.args
        payload = json.loads(content)
        source_ref = payload["project_specification"]["development_approach"][0][
            "source_refs"
        ][0]
        generated_rule = payload["project_specification"]["development_approach"][0]
        self.assertTrue(
            location.object_key.endswith("system/project_specification.json")
        )
        self.assertIn("新规则".encode(), content)
        self.assertEqual("application/json", content_type)
        self.assertEqual(file.id, source_ref["file_id"])
        self.assertEqual(file.content_hash, source_ref["content_hash"])
        self.assertEqual("pending_review", generated_rule["status"])
        prompt = generator.generate.await_args.args[0]
        self.assertIn("全部当前有效文件详情中的结构化规则候选", prompt)
        self.assertIn("source_inventory_is_complete", prompt)

    async def test_initialize_writes_empty_document_without_generator(self) -> None:
        storage = Mock()
        storage.exists.return_value = False
        service = ProjectSpecificationService(
            storage,
            StorageLocationFactory(storage_config()),
        )

        status = await service.initialize(project())

        self.assertEqual("updated", status)
        location, content, content_type = storage.put_bytes.call_args.args
        payload = json.loads(content)
        self.assertTrue(
            location.object_key.endswith("system/project_specification.json")
        )
        self.assertEqual(10, payload["project_id"])
        self.assertEqual(
            [],
            payload["project_specification"]["technical_constraints"],
        )
        self.assertEqual("application/json", content_type)

    async def test_refresh_uses_rule_candidates_beyond_twenty_files(self) -> None:
        storage = Mock()
        storage.exists.side_effect = [False, *([True] * 21)]
        files = []
        details = []
        for offset in range(21):
            file = project_file(
                file_id=100 + offset,
                relative_path=f"docs/{offset}.md",
                file_name=f"{offset}.md",
            )
            file.analysis_version = "file-detail-v1"
            file.file_type = "doc"
            file.detail_ref = f"system/file_details/{offset}.json"
            detail = file_detail(file).model_copy(
                update={
                    "detail_ref": file.detail_ref,
                    "rule_candidates": [
                        FileRuleCandidate(
                            category="document_rule",
                            text=f"文档规则 {offset}",
                            confidence="high",
                            evidence=[f"规则证据 {offset}"],
                        )
                    ],
                }
            )
            files.append(file)
            details.append(detail.model_dump_json().encode())
        storage.get_bytes.side_effect = [
            content
            for _, content in sorted(
                zip(files, details, strict=True),
                key=lambda item: item[0].relative_path,
            )
        ]
        generator = SimpleNamespace(
            generate=AsyncMock(return_value=_document("汇总规则"))
        )
        service = ProjectSpecificationService(
            storage,
            StorageLocationFactory(storage_config()),
            generator,
        )

        await service.refresh(project(), files)

        prompt = generator.generate.await_args.args[0]
        self.assertIn("文档规则 20", prompt)
        self.assertIn('"path": "docs/20.md"', prompt)

    async def test_refresh_reconciles_deleted_file_source_without_new_candidates(
        self,
    ) -> None:
        existing = _document(
            "来自已删除文件的规则",
            source_refs=[
                SpecificationSourceRef(
                    type="doc",
                    path="docs/deleted.md",
                    file_id=99,
                    content_hash="old-hash",
                    detail_ref="system/file_details/deleted.json",
                )
            ],
        )
        storage = Mock()
        storage.exists.return_value = True
        storage.get_bytes.return_value = existing.model_dump_json().encode()
        generator = SimpleNamespace(
            generate=AsyncMock(return_value=_document("已处理删除来源"))
        )
        service = ProjectSpecificationService(
            storage,
            StorageLocationFactory(storage_config()),
            generator,
        )

        status = await service.refresh(project(), [])

        self.assertEqual("updated", status)
        generator.generate.assert_awaited_once()
        prompt = generator.generate.await_args.args[0]
        self.assertIn('"current_sources": []', prompt)

    async def test_refresh_marks_changed_source_without_candidates_pending(
        self,
    ) -> None:
        existing = _document(
            "旧文件版本中的规则",
            source_refs=[
                SpecificationSourceRef(
                    type="doc",
                    path="docs/README.md",
                    file_id=30,
                    content_hash="old-content-hash",
                    detail_ref="system/file_details/old.json",
                )
            ],
        )
        file = project_file(content=b"new content")
        file.analysis_version = "file-detail-v1"
        file.file_type = "doc"
        file.detail_ref = "system/file_details/new.json"
        detail = file_detail(file).model_copy(
            update={
                "detail_ref": file.detail_ref,
                "rule_candidates": [],
            }
        )
        storage = Mock()
        storage.exists.side_effect = [True, True]
        storage.get_bytes.side_effect = [
            existing.model_dump_json().encode(),
            detail.model_dump_json().encode(),
        ]
        generator = SimpleNamespace(
            generate=AsyncMock(return_value=_document("", include_rule=False))
        )
        service = ProjectSpecificationService(
            storage,
            StorageLocationFactory(storage_config()),
            generator,
        )

        status = await service.refresh(project(), [file])

        self.assertEqual("updated", status)
        generator.generate.assert_awaited_once()
        payload = json.loads(storage.put_bytes.call_args.args[1])
        rule = payload["project_specification"]["development_approach"][0]
        self.assertEqual("pending_review", rule["status"])
        self.assertEqual(file.content_hash, rule["source_refs"][0]["content_hash"])
        self.assertEqual(file.detail_ref, rule["source_refs"][0]["detail_ref"])

    async def test_refresh_redacts_historical_candidate_before_model_call(self) -> None:
        file = project_file()
        file.analysis_version = "file-detail-v1"
        file.file_type = "doc"
        file.detail_ref = "system/file_details/current.json"
        secret = "github_pat_1234567890abcdefghijklmnop"
        detail = file_detail(file).model_copy(
            update={
                "detail_ref": file.detail_ref,
                "rule_candidates": [
                    FileRuleCandidate(
                        category="technical_constraint",
                        text=f"禁止提交凭据 {secret}",
                        confidence="high",
                        evidence=["安全规则"],
                    )
                ],
            }
        )
        storage = Mock()
        storage.exists.side_effect = [False, True]
        storage.get_bytes.return_value = detail.model_dump_json().encode()
        generator = SimpleNamespace(
            generate=AsyncMock(return_value=_document("安全规则"))
        )
        service = ProjectSpecificationService(
            storage,
            StorageLocationFactory(storage_config()),
            generator,
        )

        await service.refresh(project(), [file])

        prompt = generator.generate.await_args.args[0]
        self.assertNotIn(secret, prompt)
        self.assertIn("[已脱敏]", prompt)

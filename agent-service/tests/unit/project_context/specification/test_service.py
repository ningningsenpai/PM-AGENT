"""项目规范确定性构建服务单元测试。"""

from __future__ import annotations

import json
from datetime import datetime
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock

from app.infrastructure.storage import ObjectStorage, StorageLocationFactory
from app.project_context.file_detail.schemas import FileRuleCandidate
from app.project_context.specification.schemas import (
    DevelopmentApproachRule,
    ProjectSpecificationBody,
    ProjectSpecificationDocument,
    SpecificationSourceRef,
    merge_specifications,
)
from app.project_context.specification.service import ProjectSpecificationService
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
    human_edited: bool = False,
) -> ProjectSpecificationDocument:
    now = datetime(2026, 8, 3, 10, 0, 0)  # noqa: DTZ001 -- 模拟数据库字段。
    rules = []
    if include_rule:
        rules.append(
            DevelopmentApproachRule(
                id="development-approach-1",
                rule=rule_text,
                scope="project",
                status="active",
                confidence="high",
                source_refs=source_refs or [],
                created_at=now,
                updated_at=now,
                human_edited=human_edited,
            )
        )
    return ProjectSpecificationDocument(
        project_id=10,
        updated_at=now,
        project_specification=ProjectSpecificationBody(
            development_approach=rules,
        ),
    )


def _written_json(storage: Mock, suffix: str) -> tuple[object, bytes, str]:
    return next(
        item.args
        for item in storage.put_bytes.call_args_list
        if item.args[0].object_key.endswith(suffix)
    )


def _doc_file_with_candidates(candidates: list[FileRuleCandidate]):
    file = project_file()
    file.file_type = "doc"
    file.detail_ref = "system/file_details/current.json"
    detail = file_detail(file).model_copy(
        update={
            "detail_ref": file.detail_ref,
            "rule_candidates": candidates,
        }
    )
    return file, detail


class ProjectSpecificationServiceTest(IsolatedAsyncioTestCase):
    def test_merge_preserves_omitted_rules_and_updates_same_id(self) -> None:
        existing = _document("旧规则")
        updated = merge_specifications(existing, _document("新规则"))
        omitted = merge_specifications(existing, _document("", include_rule=False))

        self.assertEqual(
            "新规则",
            updated.project_specification.development_approach[0].rule,
        )
        self.assertEqual(
            "旧规则",
            omitted.project_specification.development_approach[0].rule,
        )

    async def test_refresh_aggregates_detail_and_stores_split_files(self) -> None:
        file, detail = _doc_file_with_candidates(
            [
                FileRuleCandidate(
                    category="technical_constraint",
                    text="后端使用 FastAPI",
                    confidence="high",
                    evidence=["架构文档明确声明"],
                )
            ]
        )
        storage = Mock(spec=ObjectStorage)
        storage.read_versioned.return_value = None
        storage.exists.return_value = True
        storage.read_bytes.return_value = detail.model_dump_json().encode()
        generator = Mock(generate=AsyncMock())
        service = ProjectSpecificationService(
            storage,
            StorageLocationFactory(storage_config()),
            generator,
        )

        status = await service.refresh(project(), [file])

        self.assertEqual("updated", status)
        generator.generate.assert_not_awaited()
        self.assertEqual(6, storage.put_bytes.call_count)
        location, content, content_type = _written_json(
            storage, "project_specification/technical_constraints.json"
        )
        payload = json.loads(content)
        rule = payload["rules"][0]
        self.assertTrue(location.object_key.endswith("technical_constraints.json"))
        self.assertEqual("后端使用 FastAPI", rule["constraint"])
        self.assertEqual("active", rule["status"])
        self.assertEqual(file.id, rule["source_refs"][0]["file_id"])
        self.assertEqual(file.content_hash, rule["source_refs"][0]["content_hash"])
        self.assertEqual("application/json", content_type)

    async def test_initialize_writes_manifest_and_five_empty_sections(self) -> None:
        storage = Mock(spec=ObjectStorage)
        storage.read_versioned.return_value = None
        service = ProjectSpecificationService(
            storage,
            StorageLocationFactory(storage_config()),
        )

        status = await service.initialize(project())

        self.assertEqual("updated", status)
        storage.read_versioned.assert_called_once()
        storage.exists.assert_not_called()
        self.assertEqual(6, storage.put_bytes.call_count)
        location, content, content_type = _written_json(
            storage, "system/project_specification.json"
        )
        payload = json.loads(content)
        self.assertTrue(location.object_key.endswith("system/project_specification.json"))
        self.assertEqual("10", payload["project_id"])
        self.assertEqual(
            0,
            payload["sections"]["technical_constraints"]["item_count"],
        )
        self.assertEqual("application/json", content_type)

    async def test_deleted_file_removes_its_derived_rule(self) -> None:
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
        storage = Mock(spec=ObjectStorage)
        storage.read_versioned.return_value = (
            existing.model_dump_json().encode(),
            "existing-etag",
        )
        generator = Mock(generate=AsyncMock())
        service = ProjectSpecificationService(
            storage,
            StorageLocationFactory(storage_config()),
            generator,
        )

        self.assertEqual("updated", await service.refresh(project(), []))

        generator.generate.assert_not_awaited()
        saved = json.loads(
            _written_json(
                storage, "project_specification/development_approach.json"
            )[1]
        )
        self.assertEqual([], saved["rules"])

    async def test_changed_file_without_candidates_removes_old_derived_rule(self) -> None:
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
        file, detail = _doc_file_with_candidates([])
        storage = Mock(spec=ObjectStorage)
        storage.read_versioned.return_value = (
            existing.model_dump_json().encode(),
            "existing-etag",
        )
        storage.exists.return_value = True
        storage.read_bytes.return_value = detail.model_dump_json().encode()
        generator = Mock(generate=AsyncMock())
        service = ProjectSpecificationService(
            storage,
            StorageLocationFactory(storage_config()),
            generator,
        )

        self.assertEqual("updated", await service.refresh(project(), [file]))

        generator.generate.assert_not_awaited()
        saved = json.loads(
            _written_json(
                storage, "project_specification/development_approach.json"
            )[1]
        )
        self.assertEqual([], saved["rules"])

    async def test_human_rule_is_preserved_during_file_snapshot_rebuild(self) -> None:
        existing = _document("用户明确设置的规则", human_edited=True)
        file, detail = _doc_file_with_candidates([])
        storage = Mock(spec=ObjectStorage)
        storage.read_versioned.return_value = (
            existing.model_dump_json().encode(),
            "existing-etag",
        )
        storage.exists.return_value = True
        storage.read_bytes.return_value = detail.model_dump_json().encode()
        service = ProjectSpecificationService(
            storage,
            StorageLocationFactory(storage_config()),
        )

        self.assertEqual("kept", await service.refresh(project(), [file]))

    async def test_candidate_secret_is_redacted_before_storage(self) -> None:
        secret = "github_pat_1234567890abcdefghijklmnop"
        file, detail = _doc_file_with_candidates(
            [
                FileRuleCandidate(
                    category="technical_constraint",
                    text=f"禁止提交凭据 {secret}",
                    confidence="high",
                    evidence=["安全规则"],
                )
            ]
        )
        storage = Mock(spec=ObjectStorage)
        storage.read_versioned.return_value = None
        storage.exists.return_value = True
        storage.read_bytes.return_value = detail.model_dump_json().encode()
        service = ProjectSpecificationService(
            storage,
            StorageLocationFactory(storage_config()),
        )

        await service.refresh(project(), [file])

        saved = json.loads(
            _written_json(
                storage, "project_specification/technical_constraints.json"
            )[1]
        )
        serialized = json.dumps(saved, ensure_ascii=False)
        self.assertNotIn(secret, serialized)
        self.assertIn("[已脱敏]", saved["rules"][0]["constraint"])

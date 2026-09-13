"""项目规范按文件来源增量同步测试。"""

from __future__ import annotations

import json
from hashlib import sha256
from unittest import IsolatedAsyncioTestCase

from app.core.errors import AppException
from app.infrastructure.storage import StorageLocation, StorageLocationFactory
from app.project_context.file_detail.schemas import (
    FileRuleCandidate,
    FileRuleCandidates,
)
from app.project_context.specification.schemas import (
    CodingRule,
    ProjectSpecificationSectionDocument,
)
from app.project_context.specification.service import (
    FileRuleSyncSource,
    ProjectSpecificationService,
)
from tests.unit.modules.project_file.factories import project, storage_config


class _VersionedMemoryStorage:
    """为规范增量发布测试提供带 ETag 的内存对象存储。"""

    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], tuple[bytes, str]] = {}
        self.counter = 0

    @staticmethod
    def _key(location: StorageLocation) -> tuple[str, str]:
        return location.bucket, location.object_key

    def read_versioned(self, location: StorageLocation):
        return self.objects.get(self._key(location))

    def compare_and_put(
        self,
        location: StorageLocation,
        content: bytes,
        etag: str | None,
    ) -> str:
        current = self.read_versioned(location)
        current_etag = current[1] if current else None
        if current_etag != etag:
            raise RuntimeError("版本冲突")
        self.counter += 1
        revision = str(self.counter)
        self.objects[self._key(location)] = content, revision
        return revision

    def remove(self, location: StorageLocation) -> None:
        self.objects.pop(self._key(location), None)


def _candidates(**sections) -> FileRuleCandidates:
    values = {
        "development_approach": [],
        "technical_constraints": [],
        "coding_rules": [],
        "document_rules": [],
        "risk_rules": [],
    }
    values.update(sections)
    return FileRuleCandidates(**values)


def _candidate(text: str, confidence: str = "high") -> FileRuleCandidate:
    return FileRuleCandidate(
        text=text,
        confidence=confidence,
        evidence=["详情文件中的明确依据"],
    )


def _source(
    file_id: int,
    rule_candidates: FileRuleCandidates,
    *,
    content_hash: str | None = None,
    may_supply_constraints: bool = True,
) -> FileRuleSyncSource:
    return FileRuleSyncSource(
        file_id=file_id,
        detail_id=f"file-{file_id}",
        detail_ref=f"system/file_details/{file_id}.json",
        source_path=f"docs/{file_id}.md",
        source_type="doc",
        content_hash=content_hash or f"hash-{file_id}",
        may_supply_constraints=may_supply_constraints,
        rule_candidates=rule_candidates,
    )


def _read_json(storage: _VersionedMemoryStorage, suffix: str) -> dict:
    return json.loads(
        next(
            content
            for (_bucket, key), (content, _etag) in storage.objects.items()
            if key.endswith(suffix)
        )
    )


class ProjectSpecificationServiceTest(IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.storage = _VersionedMemoryStorage()
        self.service = ProjectSpecificationService(
            self.storage,
            StorageLocationFactory(storage_config()),
        )

    async def test_initialize_writes_manifest_and_five_grouped_sections(self) -> None:
        self.assertEqual("updated", await self.service.initialize(project()))

        manifest = _read_json(self.storage, "system/project_specification.json")
        section = _read_json(self.storage, "project_specification/coding_rules.json")
        self.assertEqual("3.0.0", manifest["schema_version"])
        self.assertNotIn("development_stage", manifest)
        self.assertEqual({}, section["file_rule_groups"])
        self.assertEqual([], section["managed_rules"])
        self.assertEqual("kept", await self.service.initialize(project()))

    async def test_manifest_rejects_section_content_mismatch(self) -> None:
        await self.service.initialize(project())
        location = self.service._related_location(
            self.service._location(project()),
            "project_specification/coding_rules.json",
        )
        stored = self.storage.read_versioned(location)
        assert stored is not None
        section = json.loads(stored[0])
        section["updated_at"] = "2026-09-13T18:00:00+08:00"
        self.storage.compare_and_put(
            location,
            json.dumps(section, ensure_ascii=False).encode(),
            stored[1],
        )

        with self.assertRaises(AppException):
            await self.service.sync_file_sources(
                project(),
                [_source(30, _candidates(coding_rules=[_candidate("新规则")]))],
            )

    async def test_sync_uses_partitioned_detail_without_model_dependency(self) -> None:
        source = _source(
            30,
            _candidates(
                technical_constraints=[_candidate("后端使用 FastAPI")],
                coding_rules=[
                    _candidate("代码注释使用中文"),
                    _candidate("错误提示使用中文"),
                ],
            ),
        )

        self.assertEqual(
            "updated", await self.service.sync_file_sources(project(), [source])
        )

        technical = _read_json(
            self.storage, "project_specification/technical_constraints.json"
        )
        coding = _read_json(self.storage, "project_specification/coding_rules.json")
        self.assertEqual(
            "后端使用 FastAPI",
            technical["file_rule_groups"]["30"]["rules"][0]["constraint"],
        )
        self.assertEqual(2, len(coding["file_rule_groups"]["30"]["rules"]))

    async def test_reanalysis_only_replaces_current_file_groups(self) -> None:
        await self.service.sync_file_sources(
            project(),
            [
                _source(30, _candidates(coding_rules=[_candidate("旧编码规则")])),
                _source(31, _candidates(coding_rules=[_candidate("其他文件规则")])),
            ],
        )

        await self.service.sync_file_sources(
            project(),
            [
                _source(
                    30,
                    _candidates(document_rules=[_candidate("新增文档规则")]),
                    content_hash="hash-30-v2",
                )
            ],
        )

        coding = _read_json(self.storage, "project_specification/coding_rules.json")
        document = _read_json(self.storage, "project_specification/document_rules.json")
        self.assertNotIn("30", coding["file_rule_groups"])
        self.assertIn("31", coding["file_rule_groups"])
        self.assertEqual(
            "新增文档规则",
            document["file_rule_groups"]["30"]["rules"][0]["rule"],
        )

    async def test_ineligible_source_removes_all_old_groups(self) -> None:
        await self.service.sync_file_sources(
            project(),
            [_source(30, _candidates(risk_rules=[_candidate("旧风险规则")]))],
        )

        status = await self.service.sync_file_sources(
            project(),
            [_source(30, _candidates(), may_supply_constraints=False)],
        )

        self.assertEqual("updated", status)
        risk = _read_json(self.storage, "project_specification/risk_rules.json")
        self.assertNotIn("30", risk["file_rule_groups"])

    async def test_remove_file_sources_does_not_touch_other_files(self) -> None:
        await self.service.sync_file_sources(
            project(),
            [
                _source(30, _candidates(coding_rules=[_candidate("规则一")])),
                _source(31, _candidates(coding_rules=[_candidate("规则二")])),
            ],
        )

        self.assertEqual(
            "updated", await self.service.remove_file_sources(project(), [30])
        )

        coding = _read_json(self.storage, "project_specification/coding_rules.json")
        self.assertEqual({"31"}, set(coding["file_rule_groups"]))

    async def test_managed_rules_survive_file_group_replacement(self) -> None:
        await self.service.initialize(project())
        location = self.service._related_location(
            self.service._location(project()),
            "project_specification/coding_rules.json",
        )
        stored = self.storage.read_versioned(location)
        assert stored is not None
        section = ProjectSpecificationSectionDocument.model_validate_json(stored[0])
        now = section.updated_at
        managed = CodingRule(
            id="managed-rule",
            rule="用户确认规则",
            scope="project",
            status="active",
            confidence="high",
            source_refs=[],
            created_at=now,
            updated_at=now,
            human_edited=True,
        )
        updated = section.model_copy(
            update={"managed_rules": [managed.model_dump(mode="json")]}
        )
        updated_content = self.service._serialize(updated)
        self.storage.compare_and_put(
            location,
            updated_content,
            stored[1],
        )
        manifest_location = self.service._location(project())
        stored_manifest = self.storage.read_versioned(manifest_location)
        assert stored_manifest is not None
        manifest = json.loads(stored_manifest[0])
        reference = manifest["sections"]["coding_rules"]
        reference["content_hash"] = sha256(updated_content).hexdigest()
        reference["item_count"] = 1
        self.storage.compare_and_put(
            manifest_location,
            json.dumps(manifest, ensure_ascii=False).encode(),
            stored_manifest[1],
        )

        await self.service.sync_file_sources(
            project(),
            [_source(30, _candidates(coding_rules=[_candidate("文件规则")]))],
        )

        saved = _read_json(self.storage, "project_specification/coding_rules.json")
        self.assertEqual("managed-rule", saved["managed_rules"][0]["id"])

    async def test_candidate_secret_is_redacted_before_storage(self) -> None:
        secret = "github_pat_1234567890abcdefghijklmnop"

        await self.service.sync_file_sources(
            project(),
            [
                _source(
                    30,
                    _candidates(
                        technical_constraints=[_candidate(f"禁止提交凭据 {secret}")]
                    ),
                )
            ],
        )

        saved = _read_json(
            self.storage, "project_specification/technical_constraints.json"
        )
        serialized = json.dumps(saved, ensure_ascii=False)
        self.assertNotIn(secret, serialized)
        self.assertIn("[已脱敏]", serialized)

    async def test_blocked_candidate_removes_previous_file_group(self) -> None:
        await self.service.sync_file_sources(
            project(),
            [_source(30, _candidates(risk_rules=[_candidate("旧风险规则")]))],
        )

        await self.service.sync_file_sources(
            project(),
            [
                _source(
                    30,
                    _candidates(
                        risk_rules=[
                            _candidate("禁止提交 -----BEGIN PRIVATE KEY----- 测试内容")
                        ]
                    ),
                )
            ],
        )

        saved = _read_json(self.storage, "project_specification/risk_rules.json")
        self.assertNotIn("30", saved["file_rule_groups"])

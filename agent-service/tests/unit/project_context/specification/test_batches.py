"""项目规范批量增量发布回归测试。"""

from __future__ import annotations

import json
from unittest import IsolatedAsyncioTestCase

from app.core.errors import AppException
from app.infrastructure.storage import StorageLocation, StorageLocationFactory
from app.project_context.file_detail.schemas import (
    FileRuleCandidate,
    FileRuleCandidates,
)
from app.project_context.specification.schemas import (
    ProjectSpecificationSectionDocument,
    effective_section_rules,
)
from app.project_context.specification.service import (
    FileRuleSyncSource,
    ProjectSpecificationService,
)
from tests.unit.modules.project_file.factories import project, storage_config


class _VersionedMemoryStorage:
    """用于验证条件写入与失败回滚的内存对象存储。"""

    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], tuple[bytes, str]] = {}
        self.counter = 0
        self.fail_manifest = False

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
        if self.fail_manifest and location.object_key.endswith(
            "system/project_specification.json"
        ):
            raise RuntimeError("模拟清单写入失败")
        self.counter += 1
        new_etag = str(self.counter)
        self.objects[self._key(location)] = content, new_etag
        return new_etag

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


def _candidate(
    text: str,
    confidence: str = "high",
    evidence: str = "明确的文档约定",
) -> FileRuleCandidate:
    return FileRuleCandidate(
        text=text,
        confidence=confidence,
        evidence=[evidence],
    )


def _source(file_id: int, candidates: FileRuleCandidates) -> FileRuleSyncSource:
    return FileRuleSyncSource(
        file_id=file_id,
        detail_id=f"file-{file_id}",
        detail_ref=f"system/file_details/{file_id}.json",
        source_path=f"docs/{file_id}.md",
        source_type="doc",
        content_hash=f"hash-{file_id}",
        may_supply_constraints=True,
        rule_candidates=candidates,
    )


def _read_json(storage: _VersionedMemoryStorage, suffix: str) -> dict:
    return json.loads(
        next(
            content
            for (_bucket, key), (content, _etag) in storage.objects.items()
            if key.endswith(suffix)
        )
    )


class SpecificationIncrementalBatchTest(IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.storage = _VersionedMemoryStorage()
        self.service = ProjectSpecificationService(
            self.storage,
            StorageLocationFactory(storage_config()),
        )

    async def test_many_candidates_stay_in_one_file_group(self) -> None:
        candidates = [_candidate(f"候选规则 {index}") for index in range(25)]

        await self.service.sync_file_sources(
            project(), [_source(30, _candidates(coding_rules=candidates))]
        )

        section = _read_json(self.storage, "project_specification/coding_rules.json")
        rules = section["file_rule_groups"]["30"]["rules"]
        self.assertEqual(25, len(rules))
        self.assertEqual(
            {f"候选规则 {index}" for index in range(25)},
            {item["rule"] for item in rules},
        )

    async def test_effective_view_merges_same_rule_across_file_groups(self) -> None:
        await self.service.sync_file_sources(
            project(),
            [
                _source(
                    30,
                    _candidates(
                        risk_rules=[_candidate("禁止提交 API Key", "low", "安全说明")]
                    ),
                ),
                _source(
                    31,
                    _candidates(
                        risk_rules=[
                            _candidate("  禁止提交   API Key  ", "high", "开发规范")
                        ]
                    ),
                ),
            ],
        )

        section = ProjectSpecificationSectionDocument.model_validate(
            _read_json(self.storage, "project_specification/risk_rules.json")
        )
        rules = effective_section_rules(section)
        self.assertEqual(1, len(rules))
        self.assertEqual("high", rules[0].confidence)
        self.assertEqual(2, len(rules[0].source_refs))

    async def test_low_confidence_rule_waits_for_review(self) -> None:
        await self.service.sync_file_sources(
            project(),
            [
                _source(
                    30,
                    _candidates(
                        document_rules=[
                            _candidate("文档可能需要包含变更记录", "low", "措辞不明确")
                        ]
                    ),
                )
            ],
        )

        section = _read_json(self.storage, "project_specification/document_rules.json")
        rule = section["file_rule_groups"]["30"]["rules"][0]
        self.assertEqual("pending_review", rule["status"])

    async def test_manifest_does_not_embed_rule_or_development_stage(self) -> None:
        await self.service.sync_file_sources(
            project(),
            [
                _source(
                    30,
                    _candidates(technical_constraints=[_candidate("后端采用 FastAPI")]),
                )
            ],
        )

        manifest = _read_json(self.storage, "system/project_specification.json")
        serialized = json.dumps(manifest, ensure_ascii=False)
        self.assertNotIn("后端采用 FastAPI", serialized)
        self.assertNotIn("development_stage", manifest)
        self.assertEqual(
            1,
            manifest["sections"]["technical_constraints"]["item_count"],
        )

    async def test_manifest_failure_rolls_back_changed_sections(self) -> None:
        await self.service.initialize(project())
        before = dict(self.storage.objects)
        self.storage.fail_manifest = True

        with self.assertRaises(AppException):
            await self.service.sync_file_sources(
                project(),
                [
                    _source(
                        30,
                        _candidates(coding_rules=[_candidate("必须保留中文注释")]),
                    )
                ],
            )

        self.assertEqual(
            {key: value[0] for key, value in before.items()},
            {key: value[0] for key, value in self.storage.objects.items()},
        )

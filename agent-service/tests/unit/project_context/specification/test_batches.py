"""项目规范确定性聚合与分区发布回归测试。"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock

from app.infrastructure.storage import (
    ObjectStorage,
    StorageLocation,
    StorageLocationFactory,
)
from app.project_context.file_detail.schemas import FileRuleCandidate
from app.project_context.specification.schemas import (
    ProjectSpecificationSectionDocument,
)
from app.project_context.specification.service import ProjectSpecificationService
from tests.unit.modules.project_file.analysis.factories import file_detail
from tests.unit.modules.project_file.factories import (
    project,
    project_file,
    storage_config,
)


def _written_section(storage: Mock, suffix: str) -> ProjectSpecificationSectionDocument:
    call = next(
        item
        for item in storage.put_bytes.call_args_list
        if item.args[0].object_key.endswith(suffix)
    )
    return ProjectSpecificationSectionDocument.model_validate_json(call.args[1])


def _service_with_details(
    candidates_by_file: list[list[FileRuleCandidate]],
) -> tuple[ProjectSpecificationService, Mock, SimpleNamespace, list]:
    files = []
    details = []
    for offset, candidates in enumerate(candidates_by_file):
        file = project_file(
            file_id=30 + offset,
            relative_path=f"docs/{offset}.md",
            file_name=f"{offset}.md",
        )
        file.file_type = "doc"
        file.detail_ref = f"system/file_details/{offset}.json"
        files.append(file)
        details.append(
            file_detail(file).model_copy(
                update={
                    "detail_ref": file.detail_ref,
                    "rule_candidates": candidates,
                }
            )
        )
    storage = Mock(spec=ObjectStorage)
    storage.read_versioned.return_value = None
    storage.exists.return_value = True
    storage.read_bytes.side_effect = [
        detail.model_dump_json().encode()
        for _, detail in sorted(
            zip(files, details, strict=True),
            key=lambda item: item[0].relative_path,
        )
    ]
    generator = SimpleNamespace(generate=AsyncMock())
    service = ProjectSpecificationService(
        storage,
        StorageLocationFactory(storage_config()),
        generator,
    )
    return service, storage, generator, files


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

    def exists(self, location: StorageLocation) -> bool:
        return self._key(location) in self.objects

    def read_bytes(self, location: StorageLocation) -> bytes:
        return self.objects[self._key(location)][0]

    def put_bytes(
        self,
        location: StorageLocation,
        content: bytes,
        _content_type: str,
    ) -> None:
        current = self.read_versioned(location)
        self.compare_and_put(location, content, current[1] if current else None)

    def remove(self, location: StorageLocation) -> None:
        self.objects.pop(self._key(location), None)


class SpecificationDeterministicAggregationTest(IsolatedAsyncioTestCase):
    async def test_many_candidates_are_not_lost_and_do_not_call_model(self) -> None:
        candidates = [
            FileRuleCandidate(
                category="coding_rule",
                text=f"候选规则 {index}",
                confidence="high",
                evidence=["明确的文档约定"],
            )
            for index in range(25)
        ]
        service, storage, generator, files = _service_with_details([candidates])

        self.assertEqual("updated", await service.refresh(project(), files))

        generator.generate.assert_not_awaited()
        section = _written_section(
            storage, "project_specification/coding_rules.json"
        )
        self.assertEqual(25, len(section.rules))
        self.assertEqual(
            {f"候选规则 {index}" for index in range(25)},
            {item["rule"] for item in section.rules},
        )

    async def test_same_rule_merges_sources_and_uses_stronger_confidence(self) -> None:
        service, storage, generator, files = _service_with_details(
            [
                [
                    FileRuleCandidate(
                        category="risk_rule",
                        text="禁止提交 API Key",
                        confidence="low",
                        evidence=["安全说明"],
                    )
                ],
                [
                    FileRuleCandidate(
                        category="risk_rule",
                        text="  禁止提交   API Key  ",
                        confidence="high",
                        evidence=["开发规范"],
                    )
                ],
            ]
        )

        self.assertEqual("updated", await service.refresh(project(), files))

        generator.generate.assert_not_awaited()
        rule = _written_section(
            storage, "project_specification/risk_rules.json"
        ).rules[0]
        self.assertEqual("active", rule["status"])
        self.assertEqual("high", rule["confidence"])
        self.assertEqual(2, len(rule["source_refs"]))

    async def test_low_confidence_rule_waits_for_review(self) -> None:
        service, storage, _generator, files = _service_with_details(
            [
                [
                    FileRuleCandidate(
                        category="document_rule",
                        text="文档可能需要包含变更记录",
                        confidence="low",
                        evidence=["措辞不明确"],
                    )
                ]
            ]
        )

        await service.refresh(project(), files)

        rule = _written_section(
            storage, "project_specification/document_rules.json"
        ).rules[0]
        self.assertEqual("pending_review", rule["status"])
        self.assertEqual("文档可能需要包含变更记录", rule["rule"])

    async def test_manifest_does_not_embed_rule_bodies(self) -> None:
        service, storage, _generator, files = _service_with_details(
            [
                [
                    FileRuleCandidate(
                        category="technical_constraint",
                        text="后端采用 FastAPI",
                        confidence="high",
                        evidence=["架构文档"],
                    )
                ]
            ]
        )

        await service.refresh(project(), files)

        call = next(
            item
            for item in storage.put_bytes.call_args_list
            if item.args[0].object_key.endswith("system/project_specification.json")
        )
        manifest = json.loads(call.args[1])
        self.assertNotIn("project_specification", manifest)
        self.assertNotIn("后端采用 FastAPI", call.args[1].decode())
        self.assertEqual(
            1,
            manifest["sections"]["technical_constraints"]["item_count"],
        )

    async def test_manifest_failure_rolls_back_all_written_sections(self) -> None:
        storage = _VersionedMemoryStorage()
        locations = StorageLocationFactory(storage_config())
        service = ProjectSpecificationService(storage, locations)
        await service.initialize(project())
        before = dict(storage.objects)
        file = project_file()
        file.file_type = "doc"
        file.detail_ref = "system/file_details/current.json"
        detail = file_detail(file).model_copy(
            update={
                "detail_ref": file.detail_ref,
                "rule_candidates": [
                    FileRuleCandidate(
                        category="coding_rule",
                        text="必须保留中文注释",
                        confidence="high",
                        evidence=["编码规范"],
                    )
                ],
            }
        )
        detail_location = locations.system_file(
            project().owner_user_id,
            project().id,
            "file_details/current.json",
        )
        storage.put_bytes(
            detail_location,
            detail.model_dump_json().encode(),
            "application/json",
        )
        before = dict(storage.objects)
        storage.fail_manifest = True

        with self.assertRaises(RuntimeError):
            await service.refresh(project(), [file])

        self.assertEqual(
            {key: value[0] for key, value in before.items()},
            {key: value[0] for key, value in storage.objects.items()},
        )

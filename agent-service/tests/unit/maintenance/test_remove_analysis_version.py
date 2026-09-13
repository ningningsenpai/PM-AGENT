"""移除 analysis_version 维护命令单元测试。"""

from __future__ import annotations

import json
from datetime import datetime
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import AsyncMock, patch

from app.core.config import StorageConfig
from app.infrastructure.storage import StorageLocation, StorageLocationFactory
from app.maintenance.remove_analysis_version import (
    MaintenanceMigrationError,
    RemoveAnalysisVersionMigration,
    _build_parser,
    main,
)


class MemoryStorage:
    """记录维护命令对象存储副作用的内存替身。"""

    def __init__(self, objects: dict[str, bytes]) -> None:
        self.objects = dict(objects)
        self.put_calls: list[str] = []
        self.remove_calls: list[str] = []

    def exists(self, location: StorageLocation) -> bool:
        return location.object_key in self.objects

    def read_bytes(self, location: StorageLocation) -> bytes:
        return self.objects[location.object_key]

    def put_bytes(
        self,
        location: StorageLocation,
        content: bytes,
        _content_type: str,
    ) -> None:
        self.objects[location.object_key] = content
        self.put_calls.append(location.object_key)

    def list_prefix(self, location: StorageLocation) -> list[StorageLocation]:
        return [
            StorageLocation(location.bucket, object_key)
            for object_key in sorted(self.objects)
            if object_key.startswith(location.object_key)
        ]

    def remove(self, location: StorageLocation) -> None:
        self.objects.pop(location.object_key, None)
        self.remove_calls.append(location.object_key)


def _storage_config() -> StorageConfig:
    return StorageConfig(
        endpoint="127.0.0.1:9000",
        access_key="test",
        secret_key="test",
        secure=False,
        bucket="pm-agent-test",
        read_url_expiry_seconds=300,
    )


def _project() -> SimpleNamespace:
    return SimpleNamespace(
        id=10,
        owner_user_id=1,
        project_name="PM-Agent",
        created_at=datetime(2026, 8, 20, 8, 0, 0),
    )


def _file(
    file_id: int,
    *,
    detail_ref: str | None,
    content_hash: str,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=file_id,
        project_id=10,
        business_code="project",
        relative_path=f"docs/{file_id}.md",
        path_hash=f"path-{file_id}",
        file_name=f"{file_id}.md",
        extension="md",
        storage_uuid=f"{file_id:016x}",
        storage_name=f"{file_id}-{file_id:016x}.md",
        object_key=f"PM-AGENT/1/10/project/{file_id}.md",
        minio_path=f"project/{file_id}.md",
        content_type="text/markdown",
        size_bytes=10,
        source_mtime_ms=1,
        quick_fingerprint="f" * 64,
        content_hash=content_hash,
        status="active",
        upload_status="success",
        upload_attempts=1,
        parse_attempts=1,
        detail_ref=detail_ref,
        module="docs",
        kind="document",
        file_type="doc",
        language="zh-CN",
        importance="high",
        summary="测试详情",
        keywords=["测试"],
        last_error_code="OLD_ERROR",
        last_error_message="旧错误",
        last_failed_at=datetime(2026, 8, 19, 8, 0, 0),
        lock_version=0,
        created_at=datetime(2026, 8, 20, 8, 0, 0),
        updated_at=datetime(2026, 8, 20, 8, 0, 0),
    )


def _legacy_detail(file: SimpleNamespace, detail_ref: str) -> dict:
    return {
        "id": f"file-{file.id}",
        "project_id": file.project_id,
        "file_id": file.id,
        "schema_version": "1.0.0",
        "analysis_version": "file-detail-v1.0",
        "generated_at": "2026-08-20T08:00:00",
        "updated_at": "2026-08-20T08:00:00",
        "storage_uuid": file.storage_uuid,
        "storage_name": file.storage_name,
        "detail_ref": detail_ref,
        "original_path": file.relative_path,
        "minio_path": file.minio_path,
        "size_bytes": file.size_bytes,
        "content_type": file.content_type,
        "content_hash": file.content_hash,
        "module": file.module,
        "kind": file.kind,
        "file_type": file.file_type,
        "language": file.language,
        "status": "success",
        "importance": file.importance,
        "summary": file.summary,
        "keywords": file.keywords,
        "role": "项目说明",
        "content_slices": [],
        "related_topics": [],
        "related_files": [],
        "risk_flags": [],
        "sensitive_flags": [],
        "evidence": [],
        "previous_versions": [],
        "parser": {"name": "text"},
        "rule_candidates": [],
    }


def _specification(
    *,
    file_id: int,
    content_hash: str,
    detail_ref: str,
    second_hash: str | None = None,
) -> dict:
    now = "2026-08-20T08:00:00"
    references = [
        {
            "type": "doc",
            "path": f"docs/{file_id}.md",
            "file_id": file_id,
            "content_hash": content_hash,
            "detail_ref": detail_ref,
        }
    ]
    if second_hash is not None:
        references.append(
            {
                "type": "doc",
                "path": f"docs/{file_id}.md",
                "file_id": file_id,
                "content_hash": second_hash,
                "detail_ref": detail_ref,
            }
        )
    return {
        "project_id": 10,
        "schema_version": "1.0.0",
        "updated_at": now,
        "project_specification": {
            "development_stage": {},
            "development_approach": [
                {
                    "id": "rule-1",
                    "scope": "project",
                    "status": "active",
                    "confidence": "high",
                    "source_refs": references,
                    "created_at": now,
                    "updated_at": now,
                    "previous_versions": [],
                    "rule": "必须保留可追溯引用",
                }
            ],
            "technical_constraints": [],
            "coding_rules": [],
            "document_rules": [],
            "risk_rules": [],
        },
        "changes": [],
        "ignored_items": [],
    }


class RemoveAnalysisVersionMigrationTest(IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.locations = StorageLocationFactory(_storage_config())
        self.project = _project()
        self.session = AsyncMock()
        self.session.execute.return_value = SimpleNamespace(rowcount=1)
        self.index = SimpleNamespace(write=AsyncMock())

    def _location(self, relative_path: str) -> StorageLocation:
        return self.locations.system_file(1, 10, relative_path)

    def _migration(
        self,
        storage: MemoryStorage,
        files: list[SimpleNamespace],
        versions: dict[int, str | None],
    ) -> RemoveAnalysisVersionMigration:
        migration = RemoveAnalysisVersionMigration(
            self.session,
            storage,
            self.locations,
            self.index,
        )
        migration._load_legacy_versions = AsyncMock(return_value=versions)
        migration._load_projects = AsyncMock(return_value=[self.project])
        migration._load_files = AsyncMock(return_value=files)
        migration._find_remaining_legacy_refs = AsyncMock(return_value=[])
        return migration

    async def test_dry_run_has_no_write_side_effect(self) -> None:
        old_ref = "system/file_details/legacy.json"
        file = _file(30, detail_ref=old_ref, content_hash="a" * 64)
        old_location = self._location("file_details/legacy.json")
        storage = MemoryStorage(
            {
                old_location.object_key: json.dumps(
                    _legacy_detail(file, old_ref)
                ).encode()
            }
        )
        migration = self._migration(
            storage,
            [file],
            {file.id: "file-detail-v1.0"},
        )

        summary = await migration.run(apply=False)

        self.assertEqual("dry-run", summary.mode)
        self.assertEqual(1, summary.details_to_migrate)
        self.assertEqual(1, summary.objects_to_remove)
        self.assertEqual([], storage.put_calls)
        self.assertEqual([], storage.remove_calls)
        self.assertEqual(old_ref, file.detail_ref)
        self.session.flush.assert_not_awaited()
        self.session.commit.assert_awaited_once()
        self.index.write.assert_not_awaited()

    async def test_apply_migrates_exact_reference_and_is_idempotent(self) -> None:
        old_ref = "system/file_details/legacy.json"
        file = _file(30, detail_ref=old_ref, content_hash="a" * 64)
        old_location = self._location("file_details/legacy.json")
        specification_location = self._location("project_specification.json")
        storage = MemoryStorage(
            {
                old_location.object_key: json.dumps(
                    _legacy_detail(file, old_ref)
                ).encode(),
                specification_location.object_key: json.dumps(
                    _specification(
                        file_id=file.id,
                        content_hash=file.content_hash,
                        detail_ref=old_ref,
                        second_hash="b" * 64,
                    )
                ).encode(),
            }
        )
        migration = self._migration(
            storage,
            [file],
            {file.id: "file-detail-v1.0"},
        )

        first = await migration.run(apply=True)

        expected_ref = (
            "system/file_details/"
            f"{file.storage_uuid}-{file.content_hash}-{file.path_hash}.json"
        )
        new_location = self._location(expected_ref.removeprefix("system/"))
        detail = json.loads(storage.objects[new_location.object_key])
        specification = json.loads(storage.objects[specification_location.object_key])
        references = specification["project_specification"]["development_approach"][0][
            "source_refs"
        ]

        self.assertEqual(expected_ref, file.detail_ref)
        self.assertEqual("3.0.0", detail["schema_version"])
        self.assertEqual([], detail["rule_candidates"]["coding_rules"])
        self.assertNotIn("analysis_version", detail)
        self.assertEqual(expected_ref, detail["detail_ref"])
        self.assertEqual(expected_ref, references[0]["detail_ref"])
        self.assertEqual(old_ref, references[1]["detail_ref"])
        self.assertNotIn(old_location.object_key, storage.objects)
        self.assertEqual(1, first.details_migrated)
        self.assertEqual(1, first.specification_refs_updated)
        self.index.write.assert_awaited_once_with(self.project, [file])

        second = await migration.run(apply=True)

        self.assertEqual(0, second.details_to_migrate)
        self.assertEqual(1, second.details_already_current)
        self.assertEqual(0, second.objects_to_remove)
        self.assertEqual(0, second.specification_refs_updated)
        self.assertEqual(2, self.index.write.await_count)

    async def test_bad_and_versionless_details_are_invalidated(self) -> None:
        bad_ref = "system/file_details/bad.json"
        empty_version_ref = "system/file_details/versionless.json"
        bad_file = _file(30, detail_ref=bad_ref, content_hash="a" * 64)
        versionless_file = _file(
            31,
            detail_ref=empty_version_ref,
            content_hash="c" * 64,
        )
        bad_location = self._location("file_details/bad.json")
        versionless_location = self._location("file_details/versionless.json")
        specification_location = self._location("project_specification.json")
        storage = MemoryStorage(
            {
                bad_location.object_key: b"{not-json",
                versionless_location.object_key: b"{}",
                specification_location.object_key: json.dumps(
                    _specification(
                        file_id=bad_file.id,
                        content_hash=bad_file.content_hash,
                        detail_ref=bad_ref,
                        second_hash="b" * 64,
                    )
                ).encode(),
            }
        )
        migration = self._migration(
            storage,
            [bad_file, versionless_file],
            {bad_file.id: "file-detail-v1.0", versionless_file.id: None},
        )

        summary = await migration.run(apply=True)

        specification = json.loads(storage.objects[specification_location.object_key])
        rule = specification["project_specification"]["development_approach"][0]
        self.assertEqual(2, summary.details_invalidated)
        self.assertEqual(2, len(summary.invalidations))
        self.assertEqual("pending_review", rule["status"])
        self.assertEqual("", rule["source_refs"][0]["detail_ref"])
        self.assertEqual(bad_file.id, rule["source_refs"][0]["file_id"])
        self.assertEqual(
            bad_file.content_hash,
            rule["source_refs"][0]["content_hash"],
        )
        self.assertEqual(bad_ref, rule["source_refs"][1]["detail_ref"])
        for file in (bad_file, versionless_file):
            self.assertIsNone(file.detail_ref)
            self.assertIsNone(file.summary)
            self.assertIsNone(file.last_error_code)
            self.assertEqual(0, file.parse_attempts)
        self.assertNotIn(bad_location.object_key, storage.objects)
        self.assertNotIn(versionless_location.object_key, storage.objects)
        self.index.write.assert_awaited_once_with(
            self.project,
            [bad_file, versionless_file],
        )
        for call in self.session.execute.await_args_list:
            statement = call.args[0]
            sql = str(statement.compile(compile_kwargs={"literal_binds": True}))
            self.assertIn("pm_project_file.lock_version", sql)
            self.assertNotIn("lock_version", sql.partition(" WHERE ")[0])

    async def test_path_identity_mismatch_invalidates_detail(self) -> None:
        old_ref = "system/file_details/legacy.json"
        file = _file(30, detail_ref=old_ref, content_hash="a" * 64)
        payload = _legacy_detail(file, old_ref)
        payload["original_path"] = "docs/old-name.md"
        old_location = self._location("file_details/legacy.json")
        storage = MemoryStorage({old_location.object_key: json.dumps(payload).encode()})
        migration = self._migration(
            storage,
            [file],
            {file.id: "file-detail-v1.0"},
        )

        summary = await migration.run(apply=True)

        expected_ref = (
            "system/file_details/"
            f"{file.storage_uuid}-{file.content_hash}-{file.path_hash}.json"
        )
        new_location = self._location(expected_ref.removeprefix("system/"))
        self.assertEqual(1, summary.details_invalidated)
        self.assertIn("original_path", summary.invalidations[0].reason)
        self.assertIsNone(file.detail_ref)
        self.assertNotIn(new_location.object_key, storage.objects)
        self.assertNotIn(old_location.object_key, storage.objects)

    async def test_cas_conflict_keeps_old_object_and_skips_index(self) -> None:
        old_ref = "system/file_details/legacy.json"
        file = _file(30, detail_ref=old_ref, content_hash="a" * 64)
        old_location = self._location("file_details/legacy.json")
        storage = MemoryStorage(
            {
                old_location.object_key: json.dumps(
                    _legacy_detail(file, old_ref)
                ).encode()
            }
        )
        migration = self._migration(
            storage,
            [file],
            {file.id: "file-detail-v1.0"},
        )
        self.session.execute.return_value = SimpleNamespace(rowcount=0)

        with self.assertRaisesRegex(MaintenanceMigrationError, "CAS 更新失败"):
            await migration.run(apply=True)

        statement = self.session.execute.await_args.args[0]
        sql = str(statement.compile(compile_kwargs={"literal_binds": True}))
        self.assertIn("pm_project_file.content_hash", sql)
        self.assertIn("pm_project_file.lock_version", sql)
        self.assertIn("pm_project_file.detail_ref", sql)
        set_clause = sql.partition(" WHERE ")[0]
        self.assertNotIn("lock_version", set_clause)
        self.assertIn(old_location.object_key, storage.objects)
        self.assertEqual(old_ref, file.detail_ref)
        self.index.write.assert_not_awaited()

    async def test_remaining_legacy_reference_fails_before_cleanup(self) -> None:
        old_ref = "system/file_details/legacy.json"
        file = _file(30, detail_ref=old_ref, content_hash="a" * 64)
        old_location = self._location("file_details/legacy.json")
        storage = MemoryStorage(
            {
                old_location.object_key: json.dumps(
                    _legacy_detail(file, old_ref)
                ).encode()
            }
        )
        migration = self._migration(
            storage,
            [file],
            {file.id: "file-detail-v1.0"},
        )
        migration._find_remaining_legacy_refs = AsyncMock(return_value=[file.id])

        with self.assertRaisesRegex(
            MaintenanceMigrationError,
            "仍有数据库记录引用旧格式详情",
        ):
            await migration.run(apply=True)

        self.assertIn(old_location.object_key, storage.objects)
        self.assertEqual([], storage.remove_calls)


class RemoveAnalysisVersionCommandParserTest(TestCase):
    def test_mode_is_required_and_mutually_exclusive(self) -> None:
        parser = _build_parser()

        self.assertTrue(parser.parse_args(["--dry-run"]).dry_run)
        self.assertTrue(parser.parse_args(["--apply"]).apply)
        with self.assertRaises(SystemExit):
            parser.parse_args([])
        with self.assertRaises(SystemExit):
            parser.parse_args(["--dry-run", "--apply"])

    def test_apply_failure_returns_nonzero(self) -> None:
        with patch(
            "app.maintenance.remove_analysis_version._run_command",
            new=AsyncMock(side_effect=MaintenanceMigrationError("仍有旧引用")),
        ):
            exit_code = main(["--apply"])

        self.assertEqual(1, exit_code)

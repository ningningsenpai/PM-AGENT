"""迁移文件详情并移除 ``analysis_version`` 列的前置维护命令。"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Iterable

from pydantic import ValidationError
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import load_only

from app.core.config import get_settings
from app.infrastructure.database import get_session_factory
from app.infrastructure.storage import (
    ObjectStorage,
    StorageLocation,
    StorageLocationFactory,
    get_object_storage,
)
from app.modules.project.models import Project
from app.modules.project_file.models import ProjectFile
from app.project_context.file_detail.schemas import FileDetail
from app.project_context.index import ProjectIndexService
from app.project_context.specification.schemas import ProjectSpecificationDocument

_RULE_FIELDS = (
    "development_approach",
    "technical_constraints",
    "coding_rules",
    "document_rules",
    "risk_rules",
)
_DERIVED_FIELDS = (
    "detail_ref",
    "module",
    "kind",
    "file_type",
    "language",
    "importance",
    "summary",
    "keywords",
    "last_error_code",
    "last_error_message",
    "last_failed_at",
)


class MaintenanceMigrationError(RuntimeError):
    """维护迁移无法安全继续时抛出的中文错误。"""


@dataclass(frozen=True, slots=True)
class InvalidDetail:
    project_id: int
    file_id: int
    detail_ref: str | None
    reason: str


@dataclass(frozen=True, slots=True)
class DetailMigration:
    file: ProjectFile
    old_ref: str
    new_ref: str
    content: bytes
    needs_write: bool
    needs_database_update: bool


@dataclass(frozen=True, slots=True)
class SpecificationUpdate:
    location: StorageLocation
    content: bytes
    reference_count: int
    review_count: int


@dataclass(slots=True)
class ProjectPlan:
    project: Project
    files: list[ProjectFile]
    migrations: list[DetailMigration] = field(default_factory=list)
    invalid_details: list[InvalidDetail] = field(default_factory=list)
    specification: SpecificationUpdate | None = None
    stale_objects: list[StorageLocation] = field(default_factory=list)
    current_count: int = 0


@dataclass(slots=True)
class MigrationSummary:
    mode: str
    projects_scanned: int = 0
    files_scanned: int = 0
    details_to_migrate: int = 0
    details_migrated: int = 0
    details_already_current: int = 0
    details_to_invalidate: int = 0
    details_invalidated: int = 0
    specification_refs_to_update: int = 0
    specification_refs_updated: int = 0
    rules_to_review: int = 0
    rules_reviewed: int = 0
    indexes_to_rebuild: int = 0
    indexes_rebuilt: int = 0
    objects_to_remove: int = 0
    objects_removed: int = 0
    invalidations: list[InvalidDetail] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)


class RemoveAnalysisVersionMigration:
    """在删列前迁移 MinIO 详情、引用和数据库投影。"""

    def __init__(
        self,
        session: AsyncSession,
        storage: ObjectStorage,
        locations: StorageLocationFactory,
        index_service: ProjectIndexService,
    ) -> None:
        self._session = session
        self._storage = storage
        self._locations = locations
        self._index = index_service

    async def run(self, *, apply: bool) -> MigrationSummary:
        """生成迁移计划，并仅在 ``apply`` 为真时落地全部项目。"""
        summary = MigrationSummary(mode="apply" if apply else "dry-run")
        legacy_versions = await self._load_legacy_versions()
        projects = await self._load_projects()
        project_files = [
            (project, await self._load_files(project.id)) for project in projects
        ]
        # 所有 MinIO I/O 均在只读数据库事务显式结束后执行。
        await self._session.commit()
        migration_time = datetime.now().isoformat()
        plans: list[ProjectPlan] = []

        for project, files in project_files:
            plan = await self._build_plan(
                project,
                files,
                legacy_versions,
                migration_time,
            )
            plans.append(plan)
            self._record_plan(summary, plan)
        if not apply:
            return summary

        for plan in plans:
            await self._apply_plan(plan, summary)

        remaining = await self._find_remaining_legacy_refs()
        if remaining:
            file_ids = "、".join(str(file_id) for file_id in remaining)
            raise MaintenanceMigrationError(
                f"迁移后仍有数据库记录引用旧格式详情，文件 ID：{file_ids}"
            )

        # 全局验证通过后才删除旧对象，任何中途失败都保留回滚依据。
        for plan in plans:
            for location in plan.stale_objects:
                await asyncio.to_thread(self._storage.remove, location)
            summary.objects_removed += len(plan.stale_objects)

        return summary

    async def _load_legacy_versions(self) -> dict[int, str | None]:
        try:
            result = await self._session.execute(
                text("SELECT id, analysis_version FROM pm_project_file ORDER BY id")
            )
        except Exception as exception:
            raise MaintenanceMigrationError(
                "无法读取 pm_project_file.analysis_version；"
                "请在执行删列 Alembic revision 前运行本维护命令"
            ) from exception
        return {int(row[0]): row[1] for row in result.all()}

    async def _load_projects(self) -> list[Project]:
        statement = (
            select(Project)
            .options(
                load_only(
                    Project.id,
                    Project.owner_user_id,
                    Project.project_name,
                    Project.status,
                    Project.created_at,
                    Project.updated_at,
                )
            )
            .order_by(Project.id)
        )
        result = await self._session.scalars(statement)
        return list(result.all())

    async def _load_files(self, project_id: int) -> list[ProjectFile]:
        result = await self._session.scalars(
            select(ProjectFile)
            .where(ProjectFile.project_id == project_id)
            .order_by(ProjectFile.id)
        )
        return list(result.all())

    async def _build_plan(
        self,
        project: Project,
        files: list[ProjectFile],
        legacy_versions: dict[int, str | None],
        migration_time: str,
    ) -> ProjectPlan:
        plan = ProjectPlan(project=project, files=files)
        replacements: dict[tuple[int, str, str], str] = {}
        invalid_sources: set[tuple[int, str, str]] = set()
        planned_refs: set[str] = set()

        for file in files:
            legacy_version = legacy_versions.get(file.id)
            outcome = await self._plan_file(project, file, legacy_version)
            if isinstance(outcome, DetailMigration):
                plan.migrations.append(outcome)
                planned_refs.add(outcome.new_ref)
                if outcome.old_ref != outcome.new_ref:
                    replacements[(file.id, file.content_hash, outcome.old_ref)] = (
                        outcome.new_ref
                    )
                if not outcome.needs_write and not outcome.needs_database_update:
                    plan.current_count += 1
                continue
            if isinstance(outcome, InvalidDetail):
                plan.invalid_details.append(outcome)
                if outcome.detail_ref:
                    invalid_sources.add(
                        (file.id, file.content_hash, outcome.detail_ref)
                    )
                continue
            if file.detail_ref:
                planned_refs.add(file.detail_ref)

        plan.specification = await self._plan_specification(
            project,
            replacements,
            invalid_sources,
            migration_time,
        )
        plan.stale_objects = await self._find_stale_objects(
            project,
            planned_refs,
        )
        return plan

    async def _plan_file(
        self,
        project: Project,
        file: ProjectFile,
        legacy_version: str | None,
    ) -> DetailMigration | InvalidDetail | None:
        old_ref = file.detail_ref
        if legacy_version is None:
            if self._has_analysis_state(file):
                return InvalidDetail(
                    project_id=project.id,
                    file_id=file.id,
                    detail_ref=old_ref,
                    reason="旧记录缺少 analysis_version，无法证明详情版本有效",
                )
            return None
        if not old_ref:
            return InvalidDetail(
                project_id=project.id,
                file_id=file.id,
                detail_ref=None,
                reason="旧记录存在 analysis_version 但缺少 detail_ref",
            )

        new_ref = self._new_detail_ref(file)
        candidates = [old_ref]
        if new_ref != old_ref:
            candidates.append(new_ref)
        failures: list[str] = []
        for candidate_ref in candidates:
            try:
                payload = await self._read_json_detail(project, candidate_ref)
                content = self._migrate_detail_payload(
                    payload,
                    file,
                    legacy_version,
                    candidate_ref,
                    new_ref,
                )
            except MaintenanceMigrationError as exception:
                failures.append(str(exception))
                continue
            return DetailMigration(
                file=file,
                old_ref=old_ref,
                new_ref=new_ref,
                content=content,
                needs_write=candidate_ref != new_ref or payload != json.loads(content),
                needs_database_update=old_ref != new_ref,
            )

        return InvalidDetail(
            project_id=project.id,
            file_id=file.id,
            detail_ref=old_ref,
            reason="；".join(failures),
        )

    async def _read_json_detail(
        self,
        project: Project,
        detail_ref: str,
    ) -> dict[str, Any]:
        location = self._detail_location(project, detail_ref)
        if not await asyncio.to_thread(self._storage.exists, location):
            raise MaintenanceMigrationError(f"详情对象不存在：{detail_ref}")
        try:
            content = await asyncio.to_thread(self._storage.read_bytes, location)
            payload = json.loads(content)
        except Exception as exception:
            raise MaintenanceMigrationError(
                f"详情对象不是有效 JSON：{detail_ref}"
            ) from exception
        if not isinstance(payload, dict):
            raise MaintenanceMigrationError(f"详情对象根节点不是对象：{detail_ref}")
        return payload

    def _migrate_detail_payload(
        self,
        payload: dict[str, Any],
        file: ProjectFile,
        legacy_version: str,
        source_ref: str,
        new_ref: str,
    ) -> bytes:
        if source_ref == new_ref and "analysis_version" not in payload:
            migrated = dict(payload)
        else:
            if payload.get("analysis_version") != legacy_version:
                raise MaintenanceMigrationError(
                    f"详情 analysis_version 与数据库不一致：{source_ref}"
                )
            migrated = dict(payload)
            migrated.pop("analysis_version", None)
        migrated["schema_version"] = "3.0.0"
        migrated["detail_ref"] = new_ref
        legacy_candidates = migrated.get("rule_candidates")
        if isinstance(legacy_candidates, list):
            grouped_candidates = {
                "development_approach": [],
                "technical_constraints": [],
                "coding_rules": [],
                "document_rules": [],
                "risk_rules": [],
            }
            category_fields = {
                "development_approach": "development_approach",
                "technical_constraint": "technical_constraints",
                "coding_rule": "coding_rules",
                "document_rule": "document_rules",
                "risk_rule": "risk_rules",
            }
            for candidate in legacy_candidates:
                if not isinstance(candidate, dict):
                    continue
                field = category_fields.get(candidate.get("category"))
                if field is None:
                    continue
                normalized = dict(candidate)
                normalized.pop("category", None)
                grouped_candidates[field].append(normalized)
            migrated["rule_candidates"] = grouped_candidates

        expected_identity = {
            "project_id": file.project_id,
            "file_id": file.id,
            "content_hash": file.content_hash,
            "storage_uuid": file.storage_uuid,
            "storage_name": file.storage_name,
            "detail_ref": new_ref,
            "original_path": file.relative_path,
            "minio_path": file.minio_path,
            "size_bytes": file.size_bytes,
            "content_type": file.content_type,
        }
        mismatched = [
            key
            for key, value in expected_identity.items()
            if (
                str(migrated.get(key)) != str(value)
                if key == "project_id"
                else migrated.get(key) != value
            )
        ]
        if mismatched:
            fields = "、".join(mismatched)
            raise MaintenanceMigrationError(
                f"详情身份字段与数据库不一致：{source_ref}（{fields}）"
            )
        try:
            validated = FileDetail.model_validate(migrated)
        except ValidationError as exception:
            raise MaintenanceMigrationError(
                f"详情升级到 schema_version=3.0.0 后校验失败：{source_ref}"
            ) from exception
        return json.dumps(
            validated.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
        ).encode("utf-8")

    async def _plan_specification(
        self,
        project: Project,
        replacements: dict[tuple[int, str, str], str],
        invalid_sources: set[tuple[int, str, str]],
        migration_time: str,
    ) -> SpecificationUpdate | None:
        location = self._locations.system_file(
            project.owner_user_id,
            project.id,
            "project_specification.json",
        )
        if not await asyncio.to_thread(self._storage.exists, location):
            return None
        try:
            content = await asyncio.to_thread(self._storage.read_bytes, location)
            payload = json.loads(content)
            ProjectSpecificationDocument.model_validate(payload)
        except (ValidationError, ValueError, TypeError) as exception:
            raise MaintenanceMigrationError(
                f"项目 {project.id} 的 project_specification.json 格式无效"
            ) from exception
        if str(payload.get("project_id")) != str(project.id):
            raise MaintenanceMigrationError(
                f"项目 {project.id} 的 specification 项目身份不匹配"
            )

        reference_count = 0
        review_count = 0
        body = payload["project_specification"]
        for field_name in _RULE_FIELDS:
            for rule in body.get(field_name, []):
                has_invalid_source = False
                for reference in rule.get("source_refs", []):
                    key = self._source_key(reference)
                    replacement = replacements.get(key)
                    if replacement is not None:
                        reference["detail_ref"] = replacement
                        reference_count += 1
                    if key in invalid_sources:
                        reference["detail_ref"] = ""
                        reference_count += 1
                        has_invalid_source = True
                if has_invalid_source and rule.get("status") == "active":
                    rule["status"] = "pending_review"
                    rule["updated_at"] = migration_time
                    review_count += 1

        if not reference_count and not review_count:
            return None
        payload["updated_at"] = migration_time
        return SpecificationUpdate(
            location=location,
            content=json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"),
            reference_count=reference_count,
            review_count=review_count,
        )

    async def _find_stale_objects(
        self,
        project: Project,
        planned_refs: set[str],
    ) -> list[StorageLocation]:
        prefix = self._locations.system_file(
            project.owner_user_id,
            project.id,
            "file_details/",
        )
        objects = await asyncio.to_thread(self._storage.list_prefix, prefix)
        referenced_keys = {
            self._detail_location(project, detail_ref).object_key
            for detail_ref in planned_refs
        }
        return sorted(
            (
                location
                for location in objects
                if location.object_key not in referenced_keys
            ),
            key=lambda location: location.object_key,
        )

    async def _apply_plan(
        self,
        plan: ProjectPlan,
        summary: MigrationSummary,
    ) -> None:
        for migration in plan.migrations:
            if migration.needs_write:
                await asyncio.to_thread(
                    self._storage.put_bytes,
                    self._detail_location(plan.project, migration.new_ref),
                    migration.content,
                    "application/json",
                )

        if plan.specification is not None:
            await asyncio.to_thread(
                self._storage.put_bytes,
                plan.specification.location,
                plan.specification.content,
                "application/json",
            )

        await self._apply_database_changes(plan)
        await self._index.write(plan.project, plan.files)

        summary.details_migrated += sum(
            migration.needs_write or migration.needs_database_update
            for migration in plan.migrations
        )
        summary.details_invalidated += len(plan.invalid_details)
        if plan.specification is not None:
            summary.specification_refs_updated += plan.specification.reference_count
            summary.rules_reviewed += plan.specification.review_count
        summary.indexes_rebuilt += 1

    async def _apply_database_changes(self, plan: ProjectPlan) -> None:
        files_by_id = {file.id: file for file in plan.files}
        pending: list[tuple[ProjectFile, dict[str, Any]]] = []
        for migration in plan.migrations:
            if not migration.needs_database_update:
                continue
            values = {
                "detail_ref": migration.new_ref,
            }
            await self._execute_cas(
                migration.file,
                migration.old_ref,
                values,
            )
            pending.append((migration.file, values))

        for invalid in plan.invalid_details:
            file = files_by_id[invalid.file_id]
            values = {
                "detail_ref": None,
                "module": None,
                "kind": None,
                "file_type": None,
                "language": None,
                "importance": None,
                "summary": None,
                "keywords": None,
                "parse_attempts": 0,
                "last_error_code": None,
                "last_error_message": None,
                "last_failed_at": None,
            }
            await self._execute_cas(file, invalid.detail_ref, values)
            pending.append((file, values))

        if not pending:
            return
        try:
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise
        for file, values in pending:
            for name, value in values.items():
                setattr(file, name, value)

    async def _execute_cas(
        self,
        file: ProjectFile,
        expected_detail_ref: str | None,
        values: dict[str, Any],
    ) -> None:
        detail_condition = (
            ProjectFile.detail_ref.is_(None)
            if expected_detail_ref is None
            else ProjectFile.detail_ref == expected_detail_ref
        )
        statement = (
            update(ProjectFile)
            .where(
                ProjectFile.id == file.id,
                ProjectFile.project_id == file.project_id,
                ProjectFile.content_hash == file.content_hash,
                ProjectFile.lock_version == file.lock_version,
                detail_condition,
            )
            .values(**values)
            .execution_options(synchronize_session=False)
        )
        try:
            result = await self._session.execute(statement)
        except Exception:
            await self._session.rollback()
            raise
        if result.rowcount != 1:
            await self._session.rollback()
            raise MaintenanceMigrationError(
                f"文件 {file.id} 在维护期间发生变化，CAS 更新失败"
            )

    async def _find_remaining_legacy_refs(self) -> list[int]:
        try:
            result = await self._session.execute(
                text(
                    "SELECT id, storage_uuid, content_hash, path_hash, detail_ref "
                    "FROM pm_project_file WHERE detail_ref IS NOT NULL ORDER BY id"
                )
            )
            rows = result.all()
        finally:
            # 验证查询不得让后续 MinIO 清理处于数据库事务中。
            await self._session.rollback()
        remaining: list[int] = []
        for row in rows:
            expected = f"system/file_details/{row[1]}-{row[2]}-{row[3]}.json"
            if row[4] != expected:
                remaining.append(int(row[0]))
        return remaining

    @staticmethod
    def _record_plan(summary: MigrationSummary, plan: ProjectPlan) -> None:
        summary.projects_scanned += 1
        summary.files_scanned += len(plan.files)
        summary.details_to_migrate += sum(
            migration.needs_write or migration.needs_database_update
            for migration in plan.migrations
        )
        summary.details_already_current += plan.current_count
        summary.details_to_invalidate += len(plan.invalid_details)
        summary.indexes_to_rebuild += 1
        summary.objects_to_remove += len(plan.stale_objects)
        summary.invalidations.extend(plan.invalid_details)
        if plan.specification is not None:
            summary.specification_refs_to_update += plan.specification.reference_count
            summary.rules_to_review += plan.specification.review_count

    @staticmethod
    def _source_key(reference: dict[str, Any]) -> tuple[int, str, str] | None:
        file_id = reference.get("file_id")
        content_hash = reference.get("content_hash")
        detail_ref = reference.get("detail_ref")
        if not isinstance(file_id, int):
            return None
        if not isinstance(content_hash, str) or not isinstance(detail_ref, str):
            return None
        return file_id, content_hash, detail_ref

    @staticmethod
    def _has_analysis_state(file: ProjectFile) -> bool:
        return bool(
            file.parse_attempts or any(getattr(file, name) for name in _DERIVED_FIELDS)
        )

    @staticmethod
    def _new_detail_ref(file: ProjectFile) -> str:
        return (
            "system/file_details/"
            f"{file.storage_uuid}-{file.content_hash}-{file.path_hash}.json"
        )

    def _detail_location(
        self,
        project: Project,
        detail_ref: str,
    ) -> StorageLocation:
        if not detail_ref.startswith("system/file_details/"):
            raise MaintenanceMigrationError(
                f"详情引用不在 system/file_details/ 下：{detail_ref}"
            )
        return self._locations.system_file(
            project.owner_user_id,
            project.id,
            detail_ref.removeprefix("system/"),
        )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=("在维护窗口迁移旧文件详情；成功 apply 后再执行 Alembic 删列迁移")
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="只输出迁移计划，不写入")
    mode.add_argument("--apply", action="store_true", help="应用幂等迁移")
    return parser


async def _run_command(*, apply: bool) -> MigrationSummary:
    settings = get_settings()
    storage = get_object_storage()
    locations = StorageLocationFactory(settings.storage)
    async with get_session_factory()() as session:
        migration = RemoveAnalysisVersionMigration(
            session,
            storage,
            locations,
            ProjectIndexService(storage, locations),
        )
        return await migration.run(apply=apply)


def main(argv: Iterable[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        summary = asyncio.run(_run_command(apply=args.apply))
    except Exception as exception:
        print(f"维护迁移失败：{exception}", file=sys.stderr)
        return 1
    print(summary.to_json())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

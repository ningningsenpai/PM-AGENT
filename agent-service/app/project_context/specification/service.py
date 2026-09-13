"""项目规范的确定性聚合与拆分文件发布。"""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Iterable
from hashlib import sha256
from typing import Any, Literal

from pydantic import ValidationError

from app.core.errors import AppException, ErrorCode
from app.core.logger import get_logger
from app.core.time import shanghai_now
from app.infrastructure.storage import (
    ObjectStorage,
    StorageLocation,
    StorageLocationFactory,
)
from app.project_context.file_detail.schemas import FileDetail
from app.project_context.file_detail.sensitive_content import (
    SensitiveContentBlockedError,
    sanitize_sensitive_content,
)
from app.project_context.specification.schemas import (CodingRule, DevelopmentApproachRule, DevelopmentStage,
                                                       DocumentRule, ProjectSpecificationBody,
                                                       ProjectSpecificationDocument, ProjectSpecificationManifest,
                                                       ProjectSpecificationSectionDocument, RULE_SECTION_FILES,
                                                       RiskRule, SpecificationSectionReference,
                                                       SpecificationSectionReferences, SpecificationSourceRef,
                                                       TechnicalConstraintRule)

logger = get_logger(__name__)

SpecificationRefreshStatus = Literal["updated", "kept"]

_CATEGORY_FIELDS = {
    "development_approach": "development_approach",
    "technical_constraint": "technical_constraints",
    "coding_rule": "coding_rules",
    "document_rule": "document_rules",
    "risk_rule": "risk_rules",
}
_RULE_MODELS = {
    "development_approach": (DevelopmentApproachRule, "rule"),
    "technical_constraints": (TechnicalConstraintRule, "constraint"),
    "coding_rules": (CodingRule, "rule"),
    "document_rules": (DocumentRule, "rule"),
    "risk_rules": (RiskRule, "rule"),
}


class ProjectSpecificationService:
    """把权威文档详情中的规则候选确定性聚合为五个规则快照。"""

    def __init__(
        self,
        storage: ObjectStorage,
        locations: StorageLocationFactory,
        generator=None,
    ) -> None:
        self._storage = storage
        self._locations = locations
        # 保留构造参数兼容性；规则二次聚合不再调用模型。
        self._legacy_generator = generator

    async def initialize(self, project) -> SpecificationRefreshStatus:
        """不调用模型，为新项目写入一个清单和五个合法空分区。"""
        location = self._location(project)
        existing, etag = await self._load_existing_versioned(location, project.id)
        if existing is not None:
            return "kept"
        await self._write(
            location,
            ProjectSpecificationDocument.empty(project.id),
            etag,
        )
        return "updated"

    async def refresh(
        self,
        project,
        files: Iterable[Any],
        source_files: Iterable[Any] | None = None,
    ) -> SpecificationRefreshStatus:
        """仅在权威文档变化或旧来源失效时，全量重建文件规则快照。"""
        current_files = list(files)
        changed_sources = current_files if source_files is None else list(source_files)
        location = self._location(project)
        existing, etag = await self._load_existing_versioned(location, project.id)
        inventory = self._build_inventory(current_files)
        has_changed_constraint_source = any(
            self._is_current_project_file(file) and self._may_supply_constraints(file)
            for file in changed_sources
        )
        has_stale_source = self._has_stale_file_rule(existing, inventory)
        if (
            existing is not None
            and not has_changed_constraint_source
            and not has_stale_source
        ):
            return "kept"

        try:
            # 只重读现有详情，不重新解析源文件。
            sources = await self._load_rule_sources(project, current_files)
            document = self._build_document(project, existing, sources)
            if existing is not None and self._same_body(existing, document):
                return "kept"
            await self._write(location, document, etag)
            return "updated"
        except AppException:
            raise
        except (ValidationError, ValueError, TypeError) as exception:
            logger.warning(
                "项目规范候选聚合失败 action=project.specification.refresh "
                "projectId=%s",
                project.id,
            )
            raise AppException(
                ErrorCode.PROJECT_SPECIFICATION_BUILD_FAILED
            ) from exception
        except Exception as exception:
            logger.exception(
                "项目规范构建失败 action=project.specification.refresh projectId=%s",
                project.id,
            )
            raise AppException(
                ErrorCode.PROJECT_SPECIFICATION_BUILD_FAILED
            ) from exception

    async def current(self, project) -> ProjectSpecificationDocument:
        """读取当前兼容规范快照。"""
        existing, _etag = await self._load_existing_versioned(
            self._location(project), project.id
        )
        return existing or ProjectSpecificationDocument.empty(project.id)

    def _build_document(
        self,
        project,
        existing: ProjectSpecificationDocument | None,
        sources: list[dict[str, Any]],
    ) -> ProjectSpecificationDocument:
        now = shanghai_now()
        preserved = self._preserved_rules(existing)
        generated: dict[str, dict[str, dict[str, Any]]] = {
            field: {} for field in RULE_SECTION_FILES
        }
        existing_by_id = {
            rule.id: rule
            for field in RULE_SECTION_FILES
            for rule in (
                getattr(existing.project_specification, field) if existing else []
            )
        }
        for source in sources:
            source_ref = SpecificationSourceRef.model_validate(source["source_ref"])
            for candidate in source["rule_candidates"]:
                field = _CATEGORY_FIELDS[candidate["category"]]
                try:
                    sanitized = sanitize_sensitive_content(candidate["text"])
                except SensitiveContentBlockedError:
                    logger.warning(
                        "规则候选包含私钥材料，已跳过 "
                        "action=project.specification.candidate projectId=%s",
                        project.id,
                    )
                    continue
                text = self._normalize_text(sanitized.text)
                rule_id = self._rule_id(field, text)
                accumulated = generated[field].get(rule_id)
                if accumulated is None:
                    previous = existing_by_id.get(rule_id)
                    accumulated = {
                        "id": rule_id,
                        "text": text,
                        "confidence": candidate["confidence"],
                        "source_refs": [],
                        "created_at": previous.created_at if previous else now,
                    }
                    generated[field][rule_id] = accumulated
                if source_ref not in accumulated["source_refs"]:
                    accumulated["source_refs"].append(source_ref)
                accumulated["confidence"] = self._stronger_confidence(
                    accumulated["confidence"], candidate["confidence"]
                )

        body_values: dict[str, list[Any]] = {}
        for field, (model, text_field) in _RULE_MODELS.items():
            values = list(preserved[field])
            body_values[field] = values
            preserved_ids = {rule.id for rule in values}
            for rule_id, value in sorted(generated[field].items()):
                if rule_id in preserved_ids:
                    continue
                rule = model.model_validate(
                    {
                        "id": rule_id,
                        text_field: value["text"],
                        "scope": "project",
                        "status": (
                            "active"
                            if value["confidence"] in {"high", "medium"}
                            else "pending_review"
                        ),
                        "confidence": value["confidence"],
                        "source_refs": [
                            item.model_dump(mode="json")
                            for item in value["source_refs"]
                        ],
                        "created_at": value["created_at"],
                        "updated_at": now,
                        "previous_versions": [],
                    }
                )
                body_values[field].append(rule)

        return ProjectSpecificationDocument(
            project_id=project.id,
            schema_version="2.0.0",
            updated_at=now,
            project_specification=ProjectSpecificationBody(
                development_stage=self._development_stage(sources),
                **body_values,
            ),
            changes=[],
            ignored_items=[],
        )

    @staticmethod
    def _preserved_rules(
        existing: ProjectSpecificationDocument | None,
    ) -> dict[str, list[Any]]:
        """
        从已有规则文档里挑出刷新时要原样保留的规则
            - human_edited 为真：人工修改过；
            - 有 learning_entry_id：关联了学习记录；
            - 来源引用中包含 conversation 或 project_rule：来自会话或其他项目规则。
        """
        result: dict[str, list[Any]] = {field: [] for field in RULE_SECTION_FILES}
        if existing is None:
            return result
        for field in RULE_SECTION_FILES:
            result[field] = [
                rule
                for rule in getattr(existing.project_specification, field)
                if rule.human_edited
                or rule.learning_entry_id is not None
                or any(
                    ref.type in {"conversation", "project_rule"}
                    for ref in rule.source_refs
                )
            ]
        return result

    @staticmethod
    def _development_stage(sources: list[dict[str, Any]]) -> DevelopmentStage:
        completed: list[str] = []
        in_progress: list[str] = []
        next_focus: list[str] = []
        for source in sources:
            for fact in source["project_facts"]:
                if fact.get("evidence_verified") is not True:
                    continue
                statement = str(fact.get("statement") or "").strip()
                if not statement:
                    continue
                kind = str(fact.get("kind") or "").lower()
                if any(word in kind for word in ("completed", "done", "finished")):
                    completed.append(statement)
                elif any(word in kind for word in ("progress", "current", "ongoing")):
                    in_progress.append(statement)
                elif any(word in kind for word in ("next", "goal", "planned")):
                    next_focus.append(statement)
        completed = list(dict.fromkeys(completed))[:30]
        in_progress = list(dict.fromkeys(in_progress))[:10]
        next_focus = list(dict.fromkeys(next_focus))[:20]
        return DevelopmentStage(
            current_stage="；".join(in_progress),
            stage_goal=next_focus[0] if next_focus else "",
            completed=completed,
            next_focus=next_focus,
        )

    @staticmethod
    def _same_body(
        existing: ProjectSpecificationDocument,
        generated: ProjectSpecificationDocument,
    ) -> bool:
        def comparable(document: ProjectSpecificationDocument) -> dict:
            body = document.project_specification.model_dump(mode="json")
            for field in RULE_SECTION_FILES:
                for rule in body[field]:
                    rule.pop("updated_at", None)
                    rule.pop("created_at", None)
            return body

        return comparable(existing) == comparable(generated)

    async def _load_rule_sources(
        self,
        project,
        files: Iterable[Any],
    ) -> list[dict[str, Any]]:
        """从符合条件的文件中读取已有的解析详情"""
        sources: list[dict[str, Any]] = []
        eligible = [
            file
            for file in files
            if self._is_current_project_file(file)
            and file.detail_ref
            and self._may_supply_constraints(file)
        ]
        for file in sorted(eligible, key=lambda item: item.relative_path):
            location = self._locations.system_file(
                project.owner_user_id,
                project.id,
                file.detail_ref.removeprefix("system/"),
            )
            if not await asyncio.to_thread(self._storage.exists, location):
                logger.warning(
                    "文件详情不存在，跳过规则候选 action=project.specification.source "
                    "projectId=%s fileId=%s",
                    project.id,
                    file.id,
                )
                continue
            detail_bytes = await asyncio.to_thread(self._storage.read_bytes, location)
            try:
                detail = FileDetail.model_validate_json(detail_bytes)
            except ValidationError:
                logger.warning(
                    "文件详情格式无效，跳过规则候选 "
                    "action=project.specification.source "
                    "projectId=%s fileId=%s",
                    project.id,
                    file.id,
                )
                continue
            if not self._matches_file(detail, file):
                continue
            sources.append(
                {
                    "source_ref": self._inventory_item(file),
                    "project_facts": detail.project_facts,
                    "rule_candidates": [
                        candidate.model_dump(mode="json")
                        for candidate in detail.rule_candidates
                    ],
                }
            )
        return sources

    def _has_stale_file_rule(
        self,
        existing: ProjectSpecificationDocument | None,
        inventory: list[dict[str, Any]],
    ) -> bool:
        """
        判断现有规则里引用的文件来源，是否已经失效或发生变化，从而决定是否需要刷新项目规则。
            - 如果还没有现有规则文档，返回 True，表示需要构建。
            - 如果引用的文件在当前文件清单里找不到，返回 True。
            - 如果引用中的文件 ID、路径、内容哈希或详情引用与当前文件不一致，返回 True。
            - 都匹配则返回 False。
        """
        if existing is None:
            return True
        by_id = {item["file_id"]: item for item in inventory}
        by_path = {item["path"]: item for item in inventory}
        for field in RULE_SECTION_FILES:
            for rule in getattr(existing.project_specification, field):
                for ref in rule.source_refs:
                    if ref.type not in {"doc", "code"}:
                        continue
                    source = by_id.get(ref.file_id) if ref.file_id is not None else None
                    source = source or by_path.get(ref.path)
                    if source is None or self._source_ref_changed(ref, source):
                        return True
        return False

    @staticmethod
    def _source_ref_changed(
        ref: SpecificationSourceRef,
        source: dict[str, Any],
    ) -> bool:
        return (
            ref.file_id != source["file_id"]
            or ref.path != source["path"]
            or ref.content_hash != source["content_hash"]
            or ref.detail_ref != source["detail_ref"]
        )

    def _build_inventory(self, files: Iterable[Any]) -> list[dict[str, Any]]:
        return [
            self._inventory_item(file)
            for file in sorted(files, key=lambda item: item.relative_path)
            if self._is_current_project_file(file)
        ]

    @staticmethod
    def _inventory_item(file: Any) -> dict[str, Any]:
        return {
            "type": (
                "doc"
                if ProjectSpecificationService._may_supply_constraints(file)
                else "code"
            ),
            "file_id": file.id,
            "path": file.relative_path,
            "content_hash": file.content_hash,
            "detail_ref": file.detail_ref or "",
        }

    @staticmethod
    def _is_current_project_file(file: Any) -> bool:
        return (
            file.business_code == "project"
            and file.status == "active"
            and file.upload_status == "success"
        )

    @staticmethod
    def _may_supply_constraints(file: Any) -> bool:
        """
        项目约束的来源判断函数，may_supply_constraints 标记为资格标记
        若是这个字段意外失效则根据元信息做一些兜底措施
        """
        configured = getattr(file, "may_supply_constraints", None)
        if configured is not None:
            return bool(configured)
        path = str(getattr(file, "relative_path", "")).lower()
        extension = str(getattr(file, "extension", "") or "").lower()
        return (
            getattr(file, "file_type", None) == "doc"
            or extension in {"md", "markdown", "rst", "adoc"}
            or path.startswith("docs/")
            or path.rsplit("/", 1)[-1]
            in {"readme", "readme.md", "architecture.md", "design.md"}
        )

    @staticmethod
    def _matches_file(detail: FileDetail, file: Any) -> bool:
        return (
            detail.file_id == file.id
            and detail.content_hash == file.content_hash
            and detail.detail_ref == file.detail_ref
        )

    def _location(self, project) -> StorageLocation:
        return self._locations.system_file(
            project.owner_user_id,
            project.id,
            "project_specification.json",
        )

    async def _load_existing_versioned(
        self,
        location: StorageLocation,
        project_id: int,
    ) -> tuple[ProjectSpecificationDocument | None, str | None]:
        """从存储中读取并校验项目规范文档，返回 (文档, ETag)。"""
        stored = await asyncio.to_thread(self._storage.read_versioned, location)
        if stored is None:
            return None, None
        document_bytes, etag = stored
        try:
            raw = json.loads(document_bytes)
            if "project_specification" in raw:
                document = ProjectSpecificationDocument.model_validate(raw)
            else:
                document = await self._read_split_document(
                    location,
                    project_id,
                    ProjectSpecificationManifest.model_validate(raw),
                )
        except (
            ValidationError,
            ValueError,
            json.JSONDecodeError,
            AppException,
        ) as exception:
            raise AppException(
                ErrorCode.PROJECT_SPECIFICATION_BUILD_FAILED
            ) from exception
        if document.project_id != project_id:
            raise AppException(ErrorCode.PROJECT_SPECIFICATION_BUILD_FAILED)
        return document, etag

    async def _read_split_document(
        self,
        location: StorageLocation,
        project_id: int,
        manifest: ProjectSpecificationManifest,
    ) -> ProjectSpecificationDocument:
        values: dict[str, list[Any]] = {}
        for field, (model, _text_field) in _RULE_MODELS.items():
            reference = getattr(manifest.sections, field)
            section_location = self._related_location(
                location,
                reference.path.removeprefix("system/"),
            )
            section_bytes = await asyncio.to_thread(
                self._storage.read_bytes,
                section_location,
            )
            if sha256(section_bytes).hexdigest() != reference.content_hash:
                raise ValueError("规则分区内容摘要与清单不一致")
            section = ProjectSpecificationSectionDocument.model_validate_json(
                section_bytes
            )
            if section.project_id != project_id or section.section != field:
                raise ValueError("规则分区归属不一致")
            if len(section.rules) != reference.item_count:
                raise ValueError("规则分区条目数与清单不一致")
            values[field] = [model.model_validate(item) for item in section.rules]
        return ProjectSpecificationDocument(
            project_id=project_id,
            schema_version="2.0.0",
            updated_at=manifest.updated_at,
            project_specification=ProjectSpecificationBody(
                development_stage=manifest.development_stage,
                **values,
            ),
        )

    async def _write(
        self,
        location: StorageLocation,
        document: ProjectSpecificationDocument,
        etag: str | None,
    ) -> None:
        references: dict[str, SpecificationSectionReference] = {}
        body = document.project_specification
        prepared_sections: list[tuple[StorageLocation, bytes]] = []
        for field, relative_path in RULE_SECTION_FILES.items():
            rules = getattr(body, field)
            section = ProjectSpecificationSectionDocument(
                project_id=document.project_id,
                section=field,
                updated_at=document.updated_at,
                rules=[item.model_dump(mode="json") for item in rules],
            )
            section_bytes = json.dumps(
                section.model_dump(mode="json"),
                ensure_ascii=False,
                indent=2,
            ).encode("utf-8")
            section_location = self._related_location(location, relative_path)
            prepared_sections.append((section_location, section_bytes))
            references[field] = SpecificationSectionReference(
                path=f"system/{relative_path}",
                content_hash=sha256(section_bytes).hexdigest(),
                item_count=len(rules),
            )
        manifest = ProjectSpecificationManifest(
            project_id=document.project_id,
            updated_at=document.updated_at,
            development_stage=body.development_stage,
            sections=SpecificationSectionReferences(**references),
        )
        manifest_bytes = json.dumps(
            manifest.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
        ).encode("utf-8")
        if getattr(type(self._storage), "read_versioned", None) is not None:
            backups = [
                await asyncio.to_thread(self._storage.read_versioned, item_location)
                for item_location, _content in prepared_sections
            ]
            written: list[tuple[StorageLocation, bytes, tuple[bytes, str] | None]] = []
            try:
                for (section_location, section_bytes), backup in zip(
                    prepared_sections,
                    backups,
                    strict=True,
                ):
                    await asyncio.to_thread(
                        self._storage.compare_and_put,
                        section_location,
                        section_bytes,
                        backup[1] if backup is not None else None,
                    )
                    written.append((section_location, section_bytes, backup))
                await asyncio.to_thread(
                    self._storage.compare_and_put,
                    location,
                    manifest_bytes,
                    etag,
                )
            except Exception:
                await self._rollback_sections(written)
                raise
            return
        for section_location, section_bytes in prepared_sections:
            await asyncio.to_thread(
                self._storage.put_bytes,
                section_location,
                section_bytes,
                "application/json",
            )
        await asyncio.to_thread(
            self._storage.put_bytes,
            location,
            manifest_bytes,
            "application/json",
        )

    async def _rollback_sections(
        self,
        written: list[
            tuple[StorageLocation, bytes, tuple[bytes, str] | None]
        ],
    ) -> None:
        """仅在对象仍是本轮写入版本时回滚，避免覆盖并发更新。"""
        for location, written_bytes, backup in reversed(written):
            try:
                current = await asyncio.to_thread(
                    self._storage.read_versioned,
                    location,
                )
                if current is None or current[0] != written_bytes:
                    continue
                if backup is None:
                    await asyncio.to_thread(self._storage.remove, location)
                    continue
                await asyncio.to_thread(
                    self._storage.compare_and_put,
                    location,
                    backup[0],
                    current[1],
                )
            except Exception:
                logger.exception(
                    "规则分区回滚失败 action=project.specification.rollback "
                    "objectKey=%s",
                    location.object_key,
                )

    @staticmethod
    def _related_location(
        manifest_location: StorageLocation,
        relative_path: str,
    ) -> StorageLocation:
        prefix = manifest_location.object_key.rsplit("system/", 1)[0]
        return StorageLocation(
            manifest_location.bucket,
            f"{prefix}system/{relative_path}",
        )

    @staticmethod
    def _normalize_text(value: str) -> str:
        return re.sub(r"\s+", " ", value).strip()

    @classmethod
    def _rule_id(cls, field: str, text: str) -> str:
        normalized = re.sub(r"[^0-9a-z\u3400-\u9fff]+", "", text.casefold())
        digest = sha256(f"{field}:{normalized}".encode()).hexdigest()[:24]
        return f"file-{field}-{digest}"

    @staticmethod
    def _stronger_confidence(left: str, right: str) -> str:
        order = {"low": 0, "medium": 1, "high": 2}
        return left if order[left] >= order[right] else right

"""按文件来源增量维护项目规范分区。"""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Iterable
from dataclasses import dataclass
from hashlib import sha256
from typing import Literal

from pydantic import ValidationError

from app.core.errors import AppException, ErrorCode
from app.core.logger import get_logger
from app.core.time import shanghai_now
from app.infrastructure.storage import (
    ObjectStorage,
    StorageLocation,
    StorageLocationFactory,
)
from app.project_context.file_detail.schemas import (
    FileRuleCandidate,
    FileRuleCandidates,
)
from app.project_context.file_detail.sensitive_content import (
    SensitiveContentBlockedError,
    sanitize_sensitive_content,
)
from app.project_context.specification.schemas import (
    RULE_SECTION_FILES,
    CodingRule,
    DevelopmentApproachRule,
    DocumentRule,
    FileRuleGroup,
    ProjectSpecificationManifest,
    ProjectSpecificationSectionDocument,
    RiskRule,
    SpecificationSectionReference,
    SpecificationSectionReferences,
    SpecificationSourceRef,
    TechnicalConstraintRule,
)

logger = get_logger(__name__)

SpecificationRefreshStatus = Literal["updated", "kept"]

_RULE_MODELS = {
    "development_approach": (DevelopmentApproachRule, "rule"),
    "technical_constraints": (TechnicalConstraintRule, "constraint"),
    "coding_rules": (CodingRule, "rule"),
    "document_rules": (DocumentRule, "rule"),
    "risk_rules": (RiskRule, "rule"),
}


@dataclass(frozen=True, slots=True)
class FileRuleSyncSource:
    """一次成功文件分析向规范服务提供的完整来源快照。"""

    file_id: int
    detail_id: str
    detail_ref: str
    source_path: str
    source_type: Literal["doc", "code"]
    content_hash: str
    may_supply_constraints: bool
    rule_candidates: FileRuleCandidates


@dataclass(slots=True)
class _SpecificationState:
    manifest: ProjectSpecificationManifest | None
    manifest_etag: str | None
    sections: dict[str, ProjectSpecificationSectionDocument]
    section_etags: dict[str, str | None]
    section_bytes: dict[str, bytes]


class ProjectSpecificationService:
    """按 file_id 替换详情文件提供的五类规则，并保留人工维护规则。"""

    def __init__(
        self,
        storage: ObjectStorage,
        locations: StorageLocationFactory,
    ) -> None:
        self._storage = storage
        self._locations = locations

    async def initialize(self, project) -> SpecificationRefreshStatus:
        """不调用模型，为新项目幂等创建清单和五个空规则分区。"""
        state = await self._load_state(project)
        if state.manifest is not None:
            return "kept"
        await self._publish(project, state, set(RULE_SECTION_FILES))
        return "updated"

    async def sync_file_sources(
        self,
        project,
        sources: Iterable[FileRuleSyncSource],
    ) -> SpecificationRefreshStatus:
        """以本轮详情为完整快照，按 file_id 覆盖五个规则分区。"""
        current_sources = list(sources)
        if not current_sources:
            return "kept"
        try:
            state = await self._load_state(project)
            changed_sections = self._apply_sources(state.sections, current_sources)
            if state.manifest is None:
                changed_sections.update(RULE_SECTION_FILES)
            if not changed_sections and state.manifest is not None:
                return "kept"
            await self._publish(project, state, changed_sections)
            return "updated"
        except AppException:
            raise
        except (ValidationError, ValueError, TypeError) as exception:
            logger.warning(
                "项目规范来源同步失败 action=project.specification.sync projectId=%s",
                project.id,
            )
            raise AppException(
                ErrorCode.PROJECT_SPECIFICATION_BUILD_FAILED
            ) from exception
        except Exception as exception:
            logger.exception(
                "项目规范发布失败 action=project.specification.sync projectId=%s",
                project.id,
            )
            raise AppException(
                ErrorCode.PROJECT_SPECIFICATION_BUILD_FAILED
            ) from exception

    async def remove_file_sources(
        self,
        project,
        file_ids: Iterable[int],
    ) -> SpecificationRefreshStatus:
        """从五个固定分区移除已失效或已删除文件的规则组。"""
        target_ids = {str(file_id) for file_id in file_ids}
        if not target_ids:
            return "kept"
        state = await self._load_state(project)
        changed_sections: set[str] = set()
        now = shanghai_now()
        for field, section in state.sections.items():
            groups = dict(section.file_rule_groups)
            if not target_ids.intersection(groups):
                continue
            for file_id in target_ids:
                groups.pop(file_id, None)
            state.sections[field] = section.model_copy(
                update={"file_rule_groups": groups, "updated_at": now}
            )
            changed_sections.add(field)
        if state.manifest is None:
            changed_sections.update(RULE_SECTION_FILES)
        if not changed_sections and state.manifest is not None:
            return "kept"
        await self._publish(project, state, changed_sections)
        return "updated"

    def _apply_sources(
        self,
        sections: dict[str, ProjectSpecificationSectionDocument],
        sources: list[FileRuleSyncSource],
    ) -> set[str]:
        changed_sections: set[str] = set()
        now = shanghai_now()
        for field, section in sections.items():
            groups = dict(section.file_rule_groups)
            changed = False
            for source in sources:
                key = str(source.file_id)
                before = groups.get(key)
                candidates = getattr(source.rule_candidates, field)
                if not source.may_supply_constraints or not candidates:
                    if before is not None:
                        groups.pop(key)
                        changed = True
                    continue
                after = self._build_group(field, source, candidates, before, now)
                if not after.rules:
                    if before is not None:
                        groups.pop(key)
                        changed = True
                    continue
                if before != after:
                    groups[key] = after
                    changed = True
            if not changed:
                continue
            sections[field] = section.model_copy(
                update={"file_rule_groups": groups, "updated_at": now}
            )
            changed_sections.add(field)
        return changed_sections

    def _build_group(
        self,
        field: str,
        source: FileRuleSyncSource,
        candidates: list[FileRuleCandidate],
        existing: FileRuleGroup | None,
        now,
    ) -> FileRuleGroup:
        model, text_field = _RULE_MODELS[field]
        existing_rules = {
            rule.id: rule
            for rule in (
                model.model_validate(item)
                for item in (existing.rules if existing else [])
            )
        }
        source_ref = SpecificationSourceRef(
            type=source.source_type,
            path=source.source_path,
            file_id=source.file_id,
            content_hash=source.content_hash,
            detail_ref=source.detail_ref,
        )
        accumulated: dict[str, dict] = {}
        for candidate in candidates:
            try:
                text = self._normalize_text(
                    sanitize_sensitive_content(candidate.text).text
                )
                evidence = [
                    sanitize_sensitive_content(item).text for item in candidate.evidence
                ]
            except SensitiveContentBlockedError:
                logger.warning(
                    "规则候选包含私钥材料，已跳过 "
                    "action=project.specification.candidate fileId=%s",
                    source.file_id,
                )
                continue
            if not text:
                continue
            rule_id = self._rule_id(field, text)
            value = accumulated.get(rule_id)
            if value is None:
                accumulated[rule_id] = {
                    "text": text,
                    "confidence": candidate.confidence,
                    "evidence": list(dict.fromkeys(evidence)),
                }
                continue
            value["confidence"] = self._stronger_confidence(
                value["confidence"], candidate.confidence
            )
            value["evidence"] = list(dict.fromkeys([*value["evidence"], *evidence]))[
                :20
            ]

        rules = []
        for rule_id, value in sorted(accumulated.items()):
            previous = existing_rules.get(rule_id)
            candidate_rule = model.model_validate(
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
                    "evidence": value["evidence"],
                    "source_refs": [source_ref.model_dump(mode="json")],
                    "created_at": previous.created_at if previous else now,
                    "updated_at": now,
                    "previous_versions": [],
                }
            )
            if previous is not None and self._same_rule(previous, candidate_rule):
                candidate_rule = previous
            rules.append(candidate_rule.model_dump(mode="json"))

        group = FileRuleGroup(
            file_id=source.file_id,
            detail_id=source.detail_id,
            detail_ref=source.detail_ref,
            source_path=source.source_path,
            content_hash=source.content_hash,
            updated_at=now,
            rules=rules,
        )
        if existing is not None and self._same_group(existing, group):
            return existing
        return group

    async def _load_state(self, project) -> _SpecificationState:
        manifest, manifest_etag = await self._load_manifest_versioned(
            self._location(project), project.id
        )
        sections: dict[str, ProjectSpecificationSectionDocument] = {}
        section_etags: dict[str, str | None] = {}
        section_bytes: dict[str, bytes] = {}
        for field, relative_path in RULE_SECTION_FILES.items():
            location = self._related_location(self._location(project), relative_path)
            section, etag, content = await self._load_section_versioned(
                location, project.id, field
            )
            sections[field] = section
            section_etags[field] = etag
            section_bytes[field] = content
        if manifest is not None:
            self._validate_manifest(
                manifest,
                sections,
                section_etags,
                section_bytes,
            )
        return _SpecificationState(
            manifest=manifest,
            manifest_etag=manifest_etag,
            sections=sections,
            section_etags=section_etags,
            section_bytes=section_bytes,
        )

    async def _load_manifest_versioned(
        self,
        location: StorageLocation,
        project_id: int,
    ) -> tuple[ProjectSpecificationManifest | None, str | None]:
        stored = await asyncio.to_thread(self._storage.read_versioned, location)
        if stored is None:
            return None, None
        try:
            manifest = ProjectSpecificationManifest.model_validate_json(stored[0])
        except (ValidationError, ValueError) as exception:
            raise AppException(
                ErrorCode.PROJECT_SPECIFICATION_BUILD_FAILED
            ) from exception
        if manifest.project_id != project_id:
            raise AppException(ErrorCode.PROJECT_SPECIFICATION_BUILD_FAILED)
        return manifest, stored[1]

    async def _load_section_versioned(
        self,
        location: StorageLocation,
        project_id: int,
        field: str,
    ) -> tuple[ProjectSpecificationSectionDocument, str | None, bytes]:
        stored = await asyncio.to_thread(self._storage.read_versioned, location)
        if stored is None:
            section = ProjectSpecificationSectionDocument(
                project_id=project_id,
                section=field,
                updated_at=shanghai_now(),
            )
            return section, None, self._serialize(section)
        try:
            section = ProjectSpecificationSectionDocument.model_validate_json(stored[0])
        except (ValidationError, ValueError) as exception:
            raise AppException(
                ErrorCode.PROJECT_SPECIFICATION_BUILD_FAILED
            ) from exception
        if section.project_id != project_id or section.section != field:
            raise AppException(ErrorCode.PROJECT_SPECIFICATION_BUILD_FAILED)
        return section, stored[1], stored[0]

    async def _publish(
        self,
        project,
        state: _SpecificationState,
        changed_sections: set[str],
    ) -> None:
        final_bytes = dict(state.section_bytes)
        for field in changed_sections:
            final_bytes[field] = self._serialize(state.sections[field])
        manifest = self._build_manifest(project.id, state.sections, final_bytes)
        manifest_bytes = self._serialize(manifest)
        written: list[tuple[StorageLocation, bytes, str, tuple[bytes, str] | None]] = []
        try:
            for field in RULE_SECTION_FILES:
                if field not in changed_sections:
                    continue
                location = self._related_location(
                    self._location(project), RULE_SECTION_FILES[field]
                )
                backup = (
                    (state.section_bytes[field], state.section_etags[field])
                    if state.section_etags[field] is not None
                    else None
                )
                revision = await asyncio.to_thread(
                    self._storage.compare_and_put,
                    location,
                    final_bytes[field],
                    state.section_etags[field],
                )
                written.append((location, final_bytes[field], revision, backup))
            await asyncio.to_thread(
                self._storage.compare_and_put,
                self._location(project),
                manifest_bytes,
                state.manifest_etag,
            )
        except Exception:
            await self._rollback_sections(written)
            raise

    @staticmethod
    def _build_manifest(
        project_id: int,
        sections: dict[str, ProjectSpecificationSectionDocument],
        section_bytes: dict[str, bytes],
    ) -> ProjectSpecificationManifest:
        references = {
            field: SpecificationSectionReference(
                path=f"system/{RULE_SECTION_FILES[field]}",
                content_hash=sha256(section_bytes[field]).hexdigest(),
                item_count=ProjectSpecificationService._section_item_count(
                    sections[field]
                ),
            )
            for field in RULE_SECTION_FILES
        }
        return ProjectSpecificationManifest(
            project_id=project_id,
            updated_at=shanghai_now(),
            sections=SpecificationSectionReferences(**references),
        )

    @staticmethod
    def _validate_manifest(
        manifest: ProjectSpecificationManifest,
        sections: dict[str, ProjectSpecificationSectionDocument],
        section_etags: dict[str, str | None],
        section_bytes: dict[str, bytes],
    ) -> None:
        for field, relative_path in RULE_SECTION_FILES.items():
            reference = getattr(manifest.sections, field)
            if (
                reference.path != f"system/{relative_path}"
                or section_etags[field] is None
                or reference.content_hash != sha256(section_bytes[field]).hexdigest()
                or reference.item_count
                != ProjectSpecificationService._section_item_count(sections[field])
            ):
                raise AppException(ErrorCode.PROJECT_SPECIFICATION_BUILD_FAILED)

    @staticmethod
    def _section_item_count(
        section: ProjectSpecificationSectionDocument,
    ) -> int:
        return sum(
            len(group.rules) for group in section.file_rule_groups.values()
        ) + len(section.managed_rules)

    async def _rollback_sections(
        self,
        written: list[tuple[StorageLocation, bytes, str, tuple[bytes, str] | None]],
    ) -> None:
        """清单发布失败时，只回滚仍属于本轮写入的分区。"""
        for location, written_bytes, written_etag, backup in reversed(written):
            try:
                current = await asyncio.to_thread(
                    self._storage.read_versioned, location
                )
                if (
                    current is None
                    or current[0] != written_bytes
                    or current[1] != written_etag
                ):
                    continue
                if backup is None:
                    await asyncio.to_thread(self._storage.remove, location)
                else:
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
    def _same_rule(before, after) -> bool:
        return before.model_dump(
            mode="json", exclude={"updated_at"}
        ) == after.model_dump(mode="json", exclude={"updated_at"})

    @staticmethod
    def _same_group(before: FileRuleGroup, after: FileRuleGroup) -> bool:
        return before.model_dump(
            mode="json", exclude={"updated_at"}
        ) == after.model_dump(mode="json", exclude={"updated_at"})

    def _location(self, project) -> StorageLocation:
        return self._locations.system_file(
            project.owner_user_id,
            project.id,
            "project_specification.json",
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
    def _serialize(document) -> bytes:
        return json.dumps(
            document.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
        ).encode("utf-8")

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

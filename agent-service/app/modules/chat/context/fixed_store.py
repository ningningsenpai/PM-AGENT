"""固定 system 文件的正式上下文读写。"""

from __future__ import annotations

import asyncio
import copy
import json
from dataclasses import dataclass
from hashlib import sha256

from pydantic import ValidationError

from app.core.errors import AppException, ErrorCode
from app.core.time import shanghai_now
from app.infrastructure.storage import ObjectStorage, StorageLocation
from app.project_context.specification.schemas import (
    RULE_SECTION_FILES,
    ProjectSpecificationManifest,
    ProjectSpecificationSectionDocument,
    effective_section_rules,
)

from .documents.long_term_memory import LongTermMemoryDocument
from .documents.short_term_memory import ShortTermMemoryDocument
from .documents.user_habits import UserHabitsDocument
from .migration import specification_entries, stable_id
from .schemas import EntryView

PROJECT_SPECIFICATION = "project_specification.json"
RULE_FILES = tuple(RULE_SECTION_FILES.values())
SHORT_MEMORY = "short_term_memory.json"
LONG_MEMORY = "long_term_memory.json"
UPDATE_JOURNAL = "update_journal.jsonl"
HABIT_CATEGORIES = ("work", "thinking", "specification", "tooling", "life")
HABIT_FILES = tuple(f"user_habits/{category}.json" for category in HABIT_CATEGORIES)
FORMAL_FILES = (
    PROJECT_SPECIFICATION,
    *RULE_FILES,
    SHORT_MEMORY,
    LONG_MEMORY,
    *HABIT_FILES,
)
STORED_FILES = (*FORMAL_FILES, UPDATE_JOURNAL)


@dataclass(slots=True)
class FixedContextSnapshot:
    revision: str
    entries: list[dict]
    files: dict[str, str | None]
    etag: str | None = None
    version: int = 1
    manifest: None = None


@dataclass(slots=True)
class FixedWriteReceipt:
    path: str
    revision: str
    version: int = 1


class FixedContextStore:
    """以项目固定文件作为唯一正式内容源，旧 Context 目录不参与运行期读写。"""

    def __init__(self, storage: ObjectStorage, bucket: str):
        self.storage = storage
        self.bucket = bucket

    def location(self, user_id, project_id, path) -> StorageLocation:
        if path not in STORED_FILES:
            raise AppException(ErrorCode.PARAM_INVALID, "正式上下文目标文件不合法")
        return StorageLocation(
            self.bucket, f"PM-AGENT/{int(user_id)}/{int(project_id)}/system/{path}"
        )

    async def read(self, user_id, project_id, path):
        stored = await asyncio.to_thread(
            self.storage.read_versioned, self.location(user_id, project_id, path)
        )
        if stored is None:
            return self.empty(project_id, path), None
        try:
            document = json.loads(stored[0])
        except (UnicodeDecodeError, json.JSONDecodeError) as exception:
            raise AppException(
                ErrorCode.FILE_STORAGE_ERROR, f"正式上下文文件无法读取：{path}"
            ) from exception
        self.validate_document(project_id, path, document)
        return document, stored[1]

    @staticmethod
    def empty(project_id, path):
        now = shanghai_now()
        if path == PROJECT_SPECIFICATION:
            sections = {
                field: {
                    "path": f"system/{section_path}",
                    "content_hash": "",
                    "item_count": 0,
                }
                for field, section_path in RULE_SECTION_FILES.items()
            }
            return ProjectSpecificationManifest(
                project_id=project_id,
                updated_at=now,
                sections=sections,
            ).model_dump(mode="json")
        if path in RULE_FILES:
            section = next(
                field for field, section_path in RULE_SECTION_FILES.items()
                if section_path == path
            )
            return ProjectSpecificationSectionDocument(
                project_id=project_id,
                section=section,
                updated_at=now,
            ).model_dump(mode="json")
        if path == SHORT_MEMORY:
            return ShortTermMemoryDocument(
                project_id=project_id, updated_at=now
            ).model_dump(mode="json")
        if path == LONG_MEMORY:
            return LongTermMemoryDocument(
                project_id=project_id, updated_at=now
            ).model_dump(mode="json")
        category = path.removeprefix("user_habits/").removesuffix(".json")
        return UserHabitsDocument(
            project_id=project_id, category=category, updated_at=now
        ).model_dump(mode="json")

    @staticmethod
    def validate_document(project_id, path, document):
        try:
            if path == PROJECT_SPECIFICATION:
                parsed = ProjectSpecificationManifest.model_validate(document)
            elif path in RULE_FILES:
                parsed = ProjectSpecificationSectionDocument.model_validate(document)
            elif path == SHORT_MEMORY:
                parsed = ShortTermMemoryDocument.model_validate(document)
            elif path == LONG_MEMORY:
                parsed = LongTermMemoryDocument.model_validate(document)
            else:
                parsed = UserHabitsDocument.model_validate(document)
        except ValidationError as exception:
            raise AppException(
                ErrorCode.FILE_STORAGE_ERROR, f"正式上下文文件格式错误：{path}"
            ) from exception
        if int(parsed.project_id) != int(project_id):
            raise AppException(ErrorCode.FORBIDDEN, "正式上下文文件所属项目不一致")

    async def versions(self, user_id, project_id):
        result = {}
        for path in FORMAL_FILES:
            _document, etag = await self.read(user_id, project_id, path)
            result[path] = etag
        return result

    async def snapshots(self, user_id, project_id):
        project_entries, user_entries, files = [], [], {}
        for path in FORMAL_FILES:
            document, etag = await self.read(user_id, project_id, path)
            files[path] = etag
            entries = self.document_entries(user_id, project_id, path, document)
            (user_entries if path in HABIT_FILES else project_entries).extend(entries)
        project_files = {
            path: etag for path, etag in files.items() if path not in HABIT_FILES
        }
        user_files = {path: files[path] for path in HABIT_FILES}
        return {
            f"{user_id}:{project_id}:preferences": FixedContextSnapshot(
                self.revision(user_files), user_entries, user_files
            ),
            f"{user_id}:{project_id}": FixedContextSnapshot(
                self.revision(project_files), project_entries, project_files
            ),
        }

    @staticmethod
    def revision(files):
        return sha256(
            json.dumps(files, ensure_ascii=False, sort_keys=True).encode()
        ).hexdigest()

    def document_entries(self, user_id, project_id, path, document):
        if path == PROJECT_SPECIFICATION:
            return []
        if path in RULE_FILES:
            section = ProjectSpecificationSectionDocument.model_validate(document)
            return specification_entries(
                project_id,
                {
                    "project_specification": {
                        section.section: [
                            rule.model_dump(mode="json")
                            for rule in effective_section_rules(section)
                        ]
                    }
                },
            )
        if path == SHORT_MEMORY:
            key, kind, pid = "short_term_memory", "short_memory", project_id
        elif path == LONG_MEMORY:
            key, kind, pid = "long_term_memory", "long_memory", project_id
        else:
            key, kind, pid = "user_habits", "habit", project_id
        result = []
        for index, item in enumerate(document.get(key, [])):
            result.append(
                self.normalize_item(user_id, project_id, path, index, item, kind, pid)
            )
        return result

    @staticmethod
    def normalize_item(user_id, project_id, path, index, item, kind, pid):
        if not isinstance(item, dict):
            raise AppException(
                ErrorCode.FILE_STORAGE_ERROR, f"正式上下文条目格式错误：{path}"
            )
        candidate = copy.deepcopy(item)
        try:
            entry = EntryView.model_validate(candidate)
            data = entry.model_dump(mode="json", by_alias=True)
        except ValidationError:
            content = (
                item.get("content")
                or item.get("summary")
                or item.get("habit")
                or json.dumps(item, ensure_ascii=False)
            )
            data = EntryView(
                id=stable_id(f"fixed:{user_id}:{project_id}:{path}:{index}"),
                project_id=pid,
                kind=kind,
                content=content,
                attributes={
                    "key": item.get("key") or item.get("title") or f"内容 {index + 1}",
                    "sourceType": "fixed_file",
                    "original": item,
                },
                status={
                    "active": "active",
                    "confirmed": "active",
                    "invalid": "invalid",
                    "deprecated": "invalid",
                }.get(item.get("status"), "pending"),
                version=max(1, int(item.get("version", 1))),
                source_message_id=None,
                expires_at=item.get("expires_at") or item.get("expiresAt"),
            ).model_dump(mode="json", by_alias=True)
        data["projectId"] = str(pid) if pid is not None else None
        data.setdefault("attributes", {})["targetFile"] = path
        return data

    @staticmethod
    def target_for(entry):
        target = entry.get("attributes", {}).get("targetFile")
        if target in FORMAL_FILES:
            return target
        return {
            "project_rule": RULE_SECTION_FILES[
                FixedContextStore._section(entry)
            ],
            "short_memory": SHORT_MEMORY,
            "long_memory": LONG_MEMORY,
            "habit": "user_habits/work.json",
            "term": "user_habits/specification.json"
            if entry.get("projectId") is None
            else RULE_SECTION_FILES[FixedContextStore._section(entry)],
        }[entry["kind"]]

    async def apply(self, user_id, project_id, path, changes, expected_etag):
        target_location = self.location(user_id, project_id, path)
        original_stored = await asyncio.to_thread(
            self.storage.read_versioned,
            target_location,
        )
        document, current_etag = await self.read(user_id, project_id, path)
        if original_stored is not None and original_stored[1] != current_etag:
            raise AppException(ErrorCode.RESOURCE_CONFLICT, "目标文件读取期间已变化")
        if self._already_applied(project_id, path, document, changes):
            return FixedWriteReceipt(path, current_etag or self.revision(document))
        if current_etag != expected_etag:
            raise AppException(
                ErrorCode.RESOURCE_CONFLICT, "目标文件已变化，请重新核对后确认"
            )
        if path in RULE_FILES:
            updated = self._apply_specification_section(
                project_id, path, document, changes
            )
        else:
            updated = self._apply_list_document(path, document, changes)
        body = json.dumps(updated, ensure_ascii=False, indent=2).encode("utf-8")
        revision = await asyncio.to_thread(
            self.storage.compare_and_put,
            target_location,
            body,
            current_etag,
        )
        if path in RULE_FILES:
            try:
                await self._refresh_specification_manifest(user_id, project_id)
            except Exception:
                await self._rollback_rule_section(
                    target_location,
                    body,
                    revision,
                    original_stored,
                )
                raise
        await self._append_journal(user_id, project_id, path, changes)
        return FixedWriteReceipt(path, revision)

    async def _rollback_rule_section(
        self,
        location,
        written_body,
        written_etag,
        original_stored,
    ):
        """清单更新失败时恢复规则分区的精确旧字节。"""
        current = await asyncio.to_thread(self.storage.read_versioned, location)
        if (
            current is None
            or current[0] != written_body
            or current[1] != written_etag
        ):
            return
        if original_stored is None:
            await asyncio.to_thread(self.storage.remove, location)
            return
        await asyncio.to_thread(
            self.storage.compare_and_put,
            location,
            original_stored[0],
            current[1],
        )

    async def _refresh_specification_manifest(self, user_id, project_id):
        """规则分区发布后重算清单摘要；冲突时基于最新分区重试一次。"""
        for attempt in range(2):
            manifest, manifest_etag = await self.read(
                user_id, project_id, PROJECT_SPECIFICATION
            )
            sections = {}
            for field_name, path in RULE_SECTION_FILES.items():
                stored = await asyncio.to_thread(
                    self.storage.read_versioned,
                    self.location(user_id, project_id, path),
                )
                if stored is None:
                    section = self.empty(project_id, path)
                    content = json.dumps(
                        section, ensure_ascii=False, indent=2
                    ).encode("utf-8")
                else:
                    content = stored[0]
                    section = json.loads(content.decode("utf-8"))
                parsed = ProjectSpecificationSectionDocument.model_validate(section)
                sections[field_name] = {
                    "path": f"system/{path}",
                    "content_hash": sha256(content).hexdigest(),
                    "item_count": sum(
                        len(group.rules) for group in parsed.file_rule_groups.values()
                    )
                    + len(parsed.managed_rules),
                }
            updated = {
                **manifest,
                "schema_version": "3.0.0",
                "updated_at": shanghai_now().isoformat(),
                "sections": sections,
            }
            body = json.dumps(updated, ensure_ascii=False, indent=2).encode("utf-8")
            try:
                await asyncio.to_thread(
                    self.storage.compare_and_put,
                    self.location(user_id, project_id, PROJECT_SPECIFICATION),
                    body,
                    manifest_etag,
                )
                return
            except AppException:
                if attempt:
                    raise

    def _already_applied(self, project_id, path, document, changes):
        current = {
            item["id"]: item
            for item in self.document_entries(0, project_id, path, document)
        }
        for change in changes:
            entry_id = change["entryId"]
            if change.get("delete"):
                if entry_id in current:
                    return False
                continue
            actual = current.get(entry_id)
            expected = change["after"]
            if actual is None or any(
                actual.get(field) != expected.get(field)
                for field in (
                    "id",
                    "kind",
                    "content",
                    "status",
                    "version",
                    "expiresAt",
                    "conditions",
                    "relatedEntryIds",
                )
            ):
                return False
        return True

    @staticmethod
    def _apply_list_document(path, document, changes):
        updated = copy.deepcopy(document)
        key = (
            "short_term_memory"
            if path == SHORT_MEMORY
            else "long_term_memory"
            if path == LONG_MEMORY
            else "user_habits"
        )
        items = {str(item.get("id")): item for item in updated.get(key, [])}
        order = [str(item.get("id")) for item in updated.get(key, [])]
        for change in changes:
            if change.get("delete"):
                entry_id = change["entryId"]
                items.pop(entry_id, None)
                order = [item_id for item_id in order if item_id != entry_id]
                continue
            after = copy.deepcopy(change["after"])
            entry_id = after["id"]
            if entry_id not in items:
                order.append(entry_id)
            items[entry_id] = after
        updated[key] = [items[entry_id] for entry_id in order]
        updated["changes"] = []
        updated["ignored_items"] = []
        updated["updated_at"] = shanghai_now().isoformat()
        return updated

    @staticmethod
    def _section(entry):
        attributes = entry.get("attributes", {})
        explicit = attributes.get("targetSection") or attributes.get("field")
        if explicit in {
            "development_approach",
            "technical_constraints",
            "coding_rules",
            "document_rules",
            "risk_rules",
        }:
            return explicit
        text = f"{attributes.get('key', '')} {entry.get('content', '')}".lower()
        if any(word in text for word in ("风险", "risk", "禁止")):
            return "risk_rules"
        if any(word in text for word in ("文档", "document", "markdown")):
            return "document_rules"
        if any(word in text for word in ("依赖", "框架", "版本", "环境", "constraint")):
            return "technical_constraints"
        if any(word in text for word in ("流程", "分支", "阶段", "approach")):
            return "development_approach"
        return "coding_rules"

    @classmethod
    def _apply_specification_section(cls, project_id, path, document, changes):
        updated = copy.deepcopy(document)
        section = updated["section"]
        if RULE_SECTION_FILES[section] != path:
            raise AppException(ErrorCode.FILE_STORAGE_ERROR, "规则分区路径不一致")
        rules = updated.setdefault("managed_rules", [])
        for change in changes:
            before, after = change.get("before") or {}, change["after"]
            before_attributes = before.get("attributes", {})
            after_attributes = after.get("attributes", {})
            old_section = before_attributes.get(
                "targetSection"
            ) or before_attributes.get("field")
            old_id = before_attributes.get("originalId") or f"learning-{after['id']}"
            if old_section and old_section != section:
                raise AppException(ErrorCode.PARAM_INVALID, "规则不能跨分区直接覆盖")
            rules = [item for item in rules if item.get("id") != old_id]
            actual_section = cls._section(after)
            if actual_section != section:
                raise AppException(ErrorCode.PARAM_INVALID, "规则目标分区与内容不一致")
            rule_id = after_attributes.get("originalId") or f"learning-{after['id']}"
            previous = before_attributes.get("original", {}).get(
                "previous_versions", []
            )
            rule = {
                "id": rule_id,
                "scope": (after.get("conditions") or ["项目"])[0],
                "status": {
                    "active": "active",
                    "invalid": "deprecated",
                    "pending": "pending_review",
                }[after["status"]],
                "confidence": "high",
                "source_refs": [
                    {
                        "type": "conversation",
                        "path": f"learning-draft:{after_attributes.get('draftId', '')}",
                        "file_id": None,
                        "content_hash": "",
                        "detail_ref": "",
                    }
                ],
                "created_at": before_attributes.get("original", {}).get("created_at")
                or shanghai_now().isoformat(),
                "updated_at": shanghai_now().isoformat(),
                "previous_versions": previous,
                "learning_entry_id": after["id"],
                "learning_version": after["version"],
                "human_edited": True,
                "original_kind": after_attributes.get("originalKind") or "project_rule",
            }
            rule["constraint" if section == "technical_constraints" else "rule"] = after["content"]
            rules.append(rule)
        updated["managed_rules"] = rules
        updated["updated_at"] = shanghai_now().isoformat()
        return ProjectSpecificationSectionDocument.model_validate(updated).model_dump(
            mode="json"
        )

    async def history(self, user_id, project_id):
        stored = await asyncio.to_thread(
            self.storage.read_versioned,
            self.location(user_id, project_id, UPDATE_JOURNAL),
        )
        if stored is None:
            return []
        try:
            rows = [
                json.loads(line)
                for line in stored[0].decode("utf-8").splitlines()
                if line.strip()
            ]
        except (UnicodeDecodeError, json.JSONDecodeError) as exception:
            raise AppException(ErrorCode.FILE_STORAGE_ERROR, "更新日志格式错误") from exception
        return list(reversed(rows[-200:]))

    async def _append_journal(self, user_id, project_id, path, changes):
        """保存有界更新摘要，避免把完整历史复制进每个快照文件。"""
        location = self.location(user_id, project_id, UPDATE_JOURNAL)
        stored = await asyncio.to_thread(self.storage.read_versioned, location)
        old = stored[0].decode("utf-8") if stored is not None else ""
        rows = [line for line in old.splitlines() if line.strip()]
        rows.extend(
            json.dumps(
                {
                    **copy.deepcopy(item),
                    "createdAt": shanghai_now().isoformat(),
                    "targetFile": path,
                },
                ensure_ascii=False,
            )
            for item in changes
        )
        rows = rows[-200:]
        content = ("\n".join(rows) + "\n").encode("utf-8")
        await asyncio.to_thread(
            self.storage.compare_and_put,
            location,
            content,
            stored[1] if stored is not None else None,
        )

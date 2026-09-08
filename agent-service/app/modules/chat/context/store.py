"""云端上下文唯一内容源：不可变分类文件与条件发布的版本清单。"""

from __future__ import annotations

import asyncio
import hashlib
import json
from collections import OrderedDict
from dataclasses import dataclass
from datetime import UTC, datetime
from threading import RLock

from pydantic import Field

from app.core.errors import AppException, ErrorCode
from app.core.schemas import Schema
from app.infrastructure.storage import StorageLocation

from .schemas import EntryView

KINDS = ("term", "habit", "short_memory", "long_memory", "project_rule")


def json_bytes(value) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()


def digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


class BlobRef(Schema):
    path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class ContextManifest(Schema):
    schema_version: str = "2.0.0"
    user_id: str
    project_id: str | None
    version: int = Field(ge=1)
    revision: str = Field(pattern=r"^[0-9a-f]{64}$")
    operation_id: str
    request_hash: str
    updated_at: datetime
    files: dict[str, BlobRef]
    changes: BlobRef
    previous: BlobRef | None = None


class Document(Schema):
    user_id: str
    project_id: str | None
    kind: str
    entries: list[EntryView]


class VersionCache:
    """仅缓存已校验的不可变正文；容量受限，当前版本入口始终重新读取。"""

    def __init__(self, max_bytes=8 * 1024 * 1024):
        self.max_bytes = max_bytes
        self.items = OrderedDict()
        self.size = 0
        self.lock = RLock()

    def get(self, key):
        with self.lock:
            value = self.items.get(key)
            if value is not None:
                self.items.move_to_end(key)
            return value

    def put(self, key, value):
        with self.lock:
            old = self.items.pop(key, None)
            self.size -= len(old) if old is not None else 0
            if len(value) > self.max_bytes:
                return
            self.items[key] = value
            self.size += len(value)
            while self.size > self.max_bytes:
                _, removed = self.items.popitem(last=False)
                self.size -= len(removed)


_CACHE = VersionCache()


@dataclass
class ContextSnapshot:
    manifest: ContextManifest | None
    etag: str | None
    entries: list[dict]

    @property
    def version(self):
        return self.manifest.version if self.manifest else 0

    @property
    def revision(self):
        return self.manifest.revision if self.manifest else ""


class ContextStore:
    def __init__(self, storage, bucket, cache=None):
        self.storage, self.bucket = storage, bucket
        self.cache = cache if cache is not None else _CACHE

    @staticmethod
    def prefix(user_id, project_id):
        if int(user_id) <= 0 or project_id is not None and int(project_id) <= 0:
            raise AppException(ErrorCode.PARAM_INVALID, "上下文所属范围不合法")
        return (
            f"PM-AGENT/{int(user_id)}/{int(project_id)}/system/context/"
            if project_id is not None
            else f"PM-AGENT/user_context/{int(user_id)}/context/"
        )

    def location(self, prefix, path):
        if path.startswith("/") or ".." in path.split("/") or "\\" in path:
            raise AppException(ErrorCode.FORBIDDEN, "上下文对象引用越界")
        return StorageLocation(self.bucket, prefix + path)

    async def _read(self, location):
        return await asyncio.to_thread(self.storage.read_versioned, location)

    async def immutable(self, prefix, path, content):
        location = self.location(prefix, path)
        try:
            await asyncio.to_thread(
                self.storage.compare_and_put, location, content, None
            )
        except AppException:
            existing = await self._read(location)
            if existing is None or existing[0] != content:
                raise
        return BlobRef(path=path, sha256=digest(content))

    async def blob(self, prefix, ref):
        key = (self.bucket, prefix, ref.path, ref.sha256)
        content = self.cache.get(key)
        if content is None:
            existing = await self._read(self.location(prefix, ref.path))
            if existing is None or digest(existing[0]) != ref.sha256:
                raise AppException(
                    ErrorCode.FILE_STORAGE_ERROR, "云端上下文文件缺失或校验失败"
                )
            content = existing[0]
            self.cache.put(key, content)
        return json.loads(content)

    @staticmethod
    def validate_manifest(manifest, user_id, project_id):
        expected_project = str(project_id) if project_id is not None else None
        if manifest.user_id != str(user_id) or manifest.project_id != expected_project:
            raise AppException(ErrorCode.FORBIDDEN, "云端上下文所属范围不一致")

    async def load(self, user_id, project_id):
        prefix = self.prefix(user_id, project_id)
        current = await self._read(self.location(prefix, "manifest.json"))
        if current is None:
            return ContextSnapshot(None, None, [])
        manifest = ContextManifest.model_validate_json(current[0])
        self.validate_manifest(manifest, user_id, project_id)
        entries = []
        for kind, ref in manifest.files.items():
            document = Document.model_validate(await self.blob(prefix, ref))
            if (
                document.user_id != manifest.user_id
                or document.project_id != manifest.project_id
                or document.kind != kind
            ):
                raise AppException(ErrorCode.FORBIDDEN, "分类文件所属范围不一致")
            for entry in document.entries:
                if (
                    entry.kind != kind
                    or (str(entry.project_id) if entry.project_id is not None else None)
                    != manifest.project_id
                ):
                    raise AppException(ErrorCode.FORBIDDEN, "上下文条目所属范围不一致")
                entries.append(entry.model_dump(mode="json", by_alias=True))
        return ContextSnapshot(manifest, current[1], entries)

    async def find_operation(self, user_id, project_id, manifest, operation_id):
        prefix = self.prefix(user_id, project_id)
        seen = set()
        while manifest:
            self.validate_manifest(manifest, user_id, project_id)
            if manifest.revision in seen:
                raise AppException(ErrorCode.FILE_STORAGE_ERROR, "上下文版本链存在循环")
            seen.add(manifest.revision)
            if manifest.operation_id == operation_id:
                return manifest
            manifest = (
                ContextManifest.model_validate(
                    await self.blob(prefix, manifest.previous)
                )
                if manifest.previous
                else None
            )
        return None

    async def publish(
        self, user_id, project_id, base_revision, entries, operation_id, changes
    ):
        prefix = self.prefix(user_id, project_id)
        entries = [
            EntryView.model_validate(entry).model_dump(mode="json", by_alias=True)
            for entry in entries
        ]
        request_hash = digest(json_bytes({"entries": entries, "changes": changes}))
        current = await self.load(user_id, project_id)
        applied = await self.find_operation(
            user_id, project_id, current.manifest, operation_id
        )
        if applied:
            if applied.request_hash != request_hash:
                raise AppException(
                    ErrorCode.RESOURCE_CONFLICT, "同一发布操作不能用于不同内容"
                )
            return applied
        if current.revision != base_revision:
            raise AppException(
                ErrorCode.RESOURCE_CONFLICT, "基础版本已变化，请重新查看差异后确认"
            )
        expected_project = str(project_id) if project_id is not None else None
        if any(entry["projectId"] != expected_project for entry in entries):
            raise AppException(ErrorCode.FORBIDDEN, "禁止发布其他范围的内容")
        if project_id is None and any(
            entry["kind"] not in {"habit", "term"} for entry in entries
        ):
            raise AppException(
                ErrorCode.PARAM_INVALID, "项目记忆和规范不能发布到个人通用范围"
            )
        if len({entry["id"] for entry in entries}) != len(entries):
            raise AppException(ErrorCode.PARAM_INVALID, "上下文条目 ID 重复")
        revision = digest(operation_id.encode())
        folder = f"versions/{revision}/"
        files = {}
        for kind in KINDS:
            content = json_bytes(
                {
                    "userId": str(user_id),
                    "projectId": expected_project,
                    "kind": kind,
                    "entries": [entry for entry in entries if entry["kind"] == kind],
                }
            )
            files[kind] = await self.immutable(prefix, folder + kind + ".json", content)
        change_ref = await self.immutable(
            prefix, folder + "changes.json", json_bytes(changes)
        )
        previous = None
        if current.manifest:
            previous = BlobRef(
                path=f"versions/{current.revision}/manifest.json",
                sha256=digest(
                    json_bytes(current.manifest.model_dump(mode="json", by_alias=True))
                ),
            )
        manifest = ContextManifest(
            user_id=str(user_id),
            project_id=expected_project,
            version=current.version + 1,
            revision=revision,
            operation_id=operation_id,
            request_hash=request_hash,
            updated_at=datetime.now(UTC),
            files=files,
            changes=change_ref,
            previous=previous,
        )
        prepared = await self._read(self.location(prefix, folder + "manifest.json"))
        if prepared:
            old = ContextManifest.model_validate_json(prepared[0])
            if old.request_hash != request_hash or old.previous != previous:
                raise AppException(
                    ErrorCode.RESOURCE_CONFLICT, "已准备的发布操作与本次内容不一致"
                )
            manifest = old
        body = json_bytes(manifest.model_dump(mode="json", by_alias=True))
        try:
            await self.immutable(prefix, folder + "manifest.json", body)
        except AppException:
            prepared = await self._read(self.location(prefix, folder + "manifest.json"))
            if prepared is None:
                raise
            other = ContextManifest.model_validate_json(prepared[0])
            if other.request_hash != request_hash or other.previous != previous:
                raise
            manifest = other
            body = prepared[0]
        try:
            await asyncio.to_thread(
                self.storage.compare_and_put,
                self.location(prefix, "manifest.json"),
                body,
                current.etag,
            )
        except AppException:
            latest = await self.load(user_id, project_id)
            recovered = await self.find_operation(
                user_id, project_id, latest.manifest, operation_id
            )
            if recovered and recovered.request_hash == request_hash:
                return recovered
            raise
        return manifest

    async def history(self, user_id, project_id):
        snapshot = await self.load(user_id, project_id)
        manifest, result, seen = snapshot.manifest, [], set()
        prefix = self.prefix(user_id, project_id)
        while manifest and len(result) < 200:
            if manifest.revision in seen:
                raise AppException(ErrorCode.FILE_STORAGE_ERROR, "上下文版本链存在循环")
            seen.add(manifest.revision)
            self.validate_manifest(manifest, user_id, project_id)
            result.extend(await self.blob(prefix, manifest.changes))
            manifest = (
                ContextManifest.model_validate(
                    await self.blob(prefix, manifest.previous)
                )
                if manifest.previous
                else None
            )
        return result[:200]

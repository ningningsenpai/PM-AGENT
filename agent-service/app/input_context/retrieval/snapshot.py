"""可信项目快照定位与请求级对象缓存。"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import json
from pathlib import PurePosixPath
from typing import Any

from pydantic import ValidationError

from app.core.errors import AppException
from app.infrastructure.storage import ObjectStorage, StorageLocation, StorageLocationFactory
from app.project_context.index.schemas import ProjectIndexDocument


@dataclass(frozen=True, slots=True)
class ProjectSnapshot:
    """通过身份和对象前缀校验的项目 system 快照入口。"""

    index: ProjectIndexDocument
    root_prefix: str


class ProjectSnapshotReader:
    """只允许通过已验证索引中的相对引用读取当前项目对象。"""

    def __init__(
        self,
        storage: ObjectStorage,
        locations: StorageLocationFactory,
    ) -> None:
        self._storage = storage
        self._locations = locations
        self._json_cache: dict[tuple[str, str], Any] = {}
        self._bytes_cache: dict[tuple[str, str], bytes] = {}
        self._index_cache: dict[tuple[int, int], ProjectSnapshot] = {}

    async def load(
        self,
        user_id: int,
        project_id: int,
        warnings: list[str],
    ) -> ProjectSnapshot | None:
        cache_key = (user_id, project_id)
        cached = self._index_cache.get(cache_key)
        if cached is not None:
            return cached

        standard = self._locations.project_prefix(user_id, project_id)
        padded_prefix = (
            f"{self._locations.ROOT_PREFIX}/{user_id:04d}/{project_id:04d}/"
        )
        prefixes = tuple(dict.fromkeys((standard.object_key, padded_prefix)))
        for prefix in prefixes:
            location = StorageLocation(
                standard.bucket,
                f"{prefix}system/index.json",
            )
            try:
                if not await asyncio.to_thread(self._storage.exists, location):
                    continue
                index = ProjectIndexDocument.model_validate(
                    await self.read_json(location)
                )
            except (
                AppException,
                OSError,
                UnicodeDecodeError,
                json.JSONDecodeError,
                ValidationError,
            ):
                warnings.append("项目索引无法读取或结构不合法")
                continue
            if index.project_id != project_id or index.owner_user_id != user_id:
                warnings.append("项目索引身份与当前对话不一致")
                continue
            if index.storage.bucket != location.bucket:
                warnings.append("项目索引桶名与当前存储配置不一致")
                continue
            if index.storage.object_prefix != prefix:
                warnings.append("项目索引对象前缀与实际位置不一致")
                continue
            snapshot = ProjectSnapshot(index=index, root_prefix=prefix)
            self._index_cache[cache_key] = snapshot
            return snapshot

        warnings.append("当前项目的 system/index.json 不存在")
        return None

    async def optional_json(
        self,
        snapshot: ProjectSnapshot,
        relative_path: str,
        label: str,
        warnings: list[str],
    ) -> Any | None:
        try:
            return await self.read_json(
                self.system_location(snapshot, relative_path)
            )
        except (AppException, json.JSONDecodeError, UnicodeDecodeError, ValueError):
            warnings.append(f"{label}无法读取或结构不合法")
            return None

    async def read_json(self, location: StorageLocation) -> Any:
        cache_key = (location.bucket, location.object_key)
        if cache_key not in self._json_cache:
            content = await self.read_bytes(location)
            self._json_cache[cache_key] = json.loads(content.decode("utf-8"))
        return self._json_cache[cache_key]

    async def read_bytes(self, location: StorageLocation) -> bytes:
        cache_key = (location.bucket, location.object_key)
        if cache_key not in self._bytes_cache:
            self._bytes_cache[cache_key] = await asyncio.to_thread(
                self._storage.read_bytes,
                location,
            )
        return self._bytes_cache[cache_key]

    def system_location(
        self,
        snapshot: ProjectSnapshot,
        relative_path: str,
    ) -> StorageLocation:
        path = self._safe_relative_path(relative_path)
        if not path.parts or path.parts[0] != "system":
            raise ValueError("系统上下文引用必须位于 system 目录")
        return StorageLocation(
            snapshot.index.storage.bucket,
            f"{snapshot.root_prefix}{path.as_posix()}",
        )

    def project_file_location(
        self,
        snapshot: ProjectSnapshot,
        relative_path: str,
    ) -> StorageLocation:
        path = self._safe_relative_path(relative_path)
        if not path.parts or path.parts[0] == "system":
            raise ValueError("项目文件引用不能指向 system 目录")
        return StorageLocation(
            snapshot.index.storage.bucket,
            f"{snapshot.root_prefix}{path.as_posix()}",
        )

    @staticmethod
    def _safe_relative_path(value: str) -> PurePosixPath:
        path = PurePosixPath(value)
        if not value or path.is_absolute() or ".." in path.parts or "\\" in value:
            raise ValueError("项目上下文对象引用不合法")
        return path

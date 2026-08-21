"""项目索引生成与对象存储服务。"""

from __future__ import annotations

import asyncio
from datetime import datetime
import json
from typing import Any, Iterable

from app.core.errors import AppException, ErrorCode
from app.core.logger import get_logger
from app.infrastructure.storage import ObjectStorage, StorageLocationFactory
from app.project_context.index.schemas import (
    ProjectIndexDocument,
    ProjectIndexFileEntry,
    ProjectIndexStorage,
    ProjectIndexSummary,
    ProjectIndexSystemReferences,
    ProjectIndexUploadFailure,
)

logger = get_logger(__name__)


class ProjectIndexService:
    """仅从项目和数据库文件记录生成完整快照。"""

    SCHEMA_VERSION = "2.0.0"

    def __init__(
        self,
        storage: ObjectStorage,
        locations: StorageLocationFactory,
    ) -> None:
        self._storage = storage
        self._locations = locations

    async def initialize(self, project: Any) -> None:
        """初始化 index.json 索引文件。"""
        await self.write(project, [])

    async def write(self, project: Any, files: Iterable[Any]) -> None:
        """为构建完成之后的 index.json 文件上传到对象存储中。"""
        payload = self.build(project, files)
        total_nodes = payload.summary.total_nodes
        logger.debug(
            "写入项目索引 action=project.index.write projectId=%s count=%s",
            project.id,
            total_nodes,
        )
        location = self._locations.system_file(
            project.owner_user_id,
            project.id,
            "index.json",
        )
        try:
            await asyncio.to_thread(
                self._storage.put_bytes,
                location,
                json.dumps(
                    payload.model_dump(mode="json"),
                    ensure_ascii=False,
                    indent=2,
                ).encode("utf-8"),
                "application/json",
            )
        except AppException as exception:
            logger.exception(
                "项目索引写入失败 action=project.index.write projectId=%s",
                project.id,
            )
            raise AppException(ErrorCode.PROJECT_INDEX_WRITE_FAILED) from exception
        logger.debug(
            "项目索引写入完成 action=project.index.write projectId=%s count=%s",
            project.id,
            total_nodes,
        )

    def build(self, project: Any, files: Iterable[Any]) -> ProjectIndexDocument:
        """
        构建 index.json 的快照。
        传入项目为空 -> 仅仅根据文件基础信息来创建一个专属的模板。
        传入项目不为空 -> 根据文件基础信息和项目信息来完善 index.json 文件的快照构建。
        """
        project_entries: list[ProjectIndexFileEntry] = []
        user_entries: list[ProjectIndexFileEntry] = []
        failures: list[ProjectIndexUploadFailure] = []
        total_nodes = 0

        for file in files:
            total_nodes += 1
            if file.upload_status == "not_uploaded" or file.status in {
                "upload_failed",
                "verify_required",
            }:
                failures.append(self._failure(file))
            if file.status != "active" or file.upload_status != "success":
                continue
            entry = self._entry(file)
            if file.business_code == "project":
                project_entries.append(entry)
            elif file.business_code == "user":
                user_entries.append(entry)

        prefix = self._locations.project_prefix(
            project.owner_user_id,
            project.id,
        )
        return ProjectIndexDocument(
            project_id=project.id,
            project_name=project.project_name,
            owner_user_id=project.owner_user_id,
            schema_version=self.SCHEMA_VERSION,
            generated_at=project.created_at,
            updated_at=datetime.now(),
            storage=ProjectIndexStorage(
                provider="minio",
                bucket=prefix.bucket,
                object_prefix=prefix.object_key,
                index_path="system/index.json",
            ),
            summary=ProjectIndexSummary(
                total_nodes=total_nodes,
                active_files=len(project_entries) + len(user_entries),
                fail_nodes=len(failures),
            ),
            project=project_entries,
            user=user_entries,
            upload_failures=failures,
            system=ProjectIndexSystemReferences(
                index="system/index.json",
                project_specification="system/project_specification.json",
                long_term_memory="system/long_term_memory.json",
                short_term_memory="system/short_term_memory.json",
                user_habits="system/user_habits/",
                update_journal="system/update_journal.jsonl",
            ),
        )

    @staticmethod
    def _entry(file: Any) -> ProjectIndexFileEntry:
        return ProjectIndexFileEntry(
            id=file.id,
            storage_uuid=file.storage_uuid,
            logical_path=file.relative_path,
            file_name=file.file_name,
            storage_name=file.storage_name,
            minio_path=file.minio_path,
            size_bytes=file.size_bytes,
            content_type=file.content_type,
            status=file.status,
            quick_fingerprint=f"qf:sha256:{file.quick_fingerprint}",
            content_hash=f"sha256:{file.content_hash}",
            updated_at=file.updated_at,
            detail_ref=file.detail_ref,
            module=file.module,
            kind=file.kind,
            file_type=file.file_type,
            language=file.language,
            importance=file.importance,
            summary=file.summary,
            keywords=file.keywords or [],
        )

    @staticmethod
    def _failure(file: Any) -> ProjectIndexUploadFailure:
        status = "not_uploaded" if file.upload_status == "not_uploaded" else file.status
        return ProjectIndexUploadFailure(
            file_id=file.id,
            business=file.business_code,
            logical_path=file.relative_path,
            file_name=file.file_name,
            storage_name=file.storage_name,
            status=status,
            attempts=file.upload_attempts,
            last_error_code=file.last_error_code,
            updated_at=file.updated_at,
        )

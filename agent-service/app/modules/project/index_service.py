"""项目上下文索引快照。"""
from __future__ import annotations

import asyncio
from datetime import datetime
import json
from typing import Any, Iterable

from app.core.errors import AppException, ErrorCode
from app.core.logger import get_logger
from app.infrastructure.storage import (
    ObjectStorage,
    StorageLocationFactory,
)

logger = get_logger(__name__)


class ProjectIndexService:
    """仅从项目和数据库文件记录生成完整快照。"""

    SCHEMA_VERSION = "1.0.0"

    def __init__(
        self,
        storage: ObjectStorage,
        locations: StorageLocationFactory,
    ) -> None:
        self._storage = storage
        self._locations = locations

    async def initialize(self, project) -> None:
        await self.write(project, [])

    async def write(self, project, files: Iterable[Any]) -> None:
        payload = self.build(project, files)
        total_nodes = payload["summary"]["total_nodes"]
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
                    payload,
                    ensure_ascii=False,
                    indent=2,
                    default=self._json_default,
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

    def build(self, project, files: Iterable[Any]) -> dict[str, Any]:
        project_entries: list[dict[str, Any]] = []
        user_entries: list[dict[str, Any]] = []
        failures: list[dict[str, Any]] = []
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

        now = datetime.now().isoformat()
        prefix = self._locations.project_prefix(
            project.owner_user_id,
            project.id,
        )
        return {
            "project_id": project.id,
            "project_name": project.project_name,
            "owner_user_id": project.owner_user_id,
            "schema_version": self.SCHEMA_VERSION,
            "generated_at": self._json_default(project.created_at),
            "updated_at": now,
            "storage": {
                "provider": "minio",
                "bucket": prefix.bucket,
                "object_prefix": prefix.object_key,
                "index_path": "system/index.json",
            },
            "summary": {
                "total_nodes": total_nodes,
                "active_files": len(project_entries) + len(user_entries),
                "fail_nodes": len(failures),
            },
            "project": project_entries,
            "user": user_entries,
            "upload_failures": failures,
            "system": {
                "index": "system/index.json",
                "project_specification": "system/project_specification.json",
                "long_term_memory": "system/long_term_memory.json",
                "short_term_memory": "system/short_term_memory.json",
                "user_habits": "system/user_habits/",
                "update_journal": "system/update_journal.jsonl",
            },
        }

    @staticmethod
    def _entry(file) -> dict[str, Any]:
        return {
            "id": file.id,
            "storage_uuid": file.storage_uuid,
            "logical_path": file.relative_path,
            "file_name": file.file_name,
            "storage_name": file.storage_name,
            "minio_path": file.minio_path,
            "size_bytes": file.size_bytes,
            "content_type": file.content_type,
            "status": file.status,
            "quick_fingerprint": f"qf:sha256:{file.quick_fingerprint}",
            "content_hash": f"sha256:{file.content_hash}",
            "updated_at": file.updated_at,
            "detail_ref": file.detail_ref if file.analysis_version else None,
            "analysis_version": file.analysis_version,
            "module": file.module,
            "kind": file.kind,
            "file_type": file.file_type,
            "language": file.language,
            "importance": file.importance,
            "summary": file.summary,
            "keywords": file.keywords or [],
        }

    @staticmethod
    def _failure(file) -> dict[str, Any]:
        status = (
            "not_uploaded"
            if file.upload_status == "not_uploaded"
            else file.status
        )
        return {
            "file_id": file.id,
            "business": file.business_code,
            "logical_path": file.relative_path,
            "file_name": file.file_name,
            "storage_name": file.storage_name,
            "status": status,
            "attempts": file.upload_attempts,
            "last_error_code": file.last_error_code,
            "updated_at": file.updated_at,
        }

    @staticmethod
    def _json_default(value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.isoformat()
        return str(value)

"""项目规范生成与对象存储服务。"""
from __future__ import annotations

import asyncio
import json
from typing import Any, Iterable

from pydantic import ValidationError

from app.core.errors import AppException, ErrorCode
from app.core.logger import get_logger
from app.infrastructure.storage import ObjectStorage, StorageLocationFactory
from app.project.context.model.structured import StructuredJsonGenerator
from app.project.context.specification.schemas import (
    ProjectSpecificationDocument,
    merge_specifications,
)
from app.project.inner_prompts import ProjectSpecificationPrompt

logger = get_logger(__name__)


class ProjectSpecificationService:
    """使用当前有效文件投影构建并合并项目规范。"""

    MAX_SOURCE_FILES = 20

    def __init__(
        self,
        storage: ObjectStorage,
        locations: StorageLocationFactory,
        generator: StructuredJsonGenerator,
    ) -> None:
        self._storage = storage
        self._locations = locations
        self._generator = generator

    async def refresh(self, project, files: Iterable[Any]) -> None:
        current_files = list(files)
        location = self._locations.system_file(
            project.owner_user_id,
            project.id,
            "project_specification.json",
        )
        existing = await self._load_existing(location, project.id)
        sources = self._build_sources(current_files)
        source_paths = self._build_source_paths(current_files)
        if not sources:
            if existing is None:
                await self._write(location, ProjectSpecificationDocument.empty(project.id))
                return

        prompt = self._build_prompt(project, existing, sources, source_paths)
        try:
            generated = await self._generator.generate(
                prompt,
                ProjectSpecificationDocument,
            )
            if generated.project_id != project.id:
                raise ValueError("项目规范中的项目 ID 与当前项目不一致")
            document = merge_specifications(existing, generated)
            await self._write(location, document)
        except (ValidationError, ValueError) as exception:
            logger.warning(
                "项目规范模型输出无效 action=project.specification.refresh projectId=%s",
                project.id,
            )
            raise AppException(ErrorCode.PROJECT_SPECIFICATION_BUILD_FAILED) from exception
        except AppException:
            raise
        except Exception as exception:
            logger.exception(
                "项目规范构建失败 action=project.specification.refresh projectId=%s",
                project.id,
            )
            raise AppException(ErrorCode.PROJECT_SPECIFICATION_BUILD_FAILED) from exception

    async def _load_existing(
        self,
        location,
        project_id: int,
    ) -> ProjectSpecificationDocument | None:
        exists = await asyncio.to_thread(self._storage.exists, location)
        if not exists:
            return None
        content = await asyncio.to_thread(self._storage.get_bytes, location)
        try:
            document = ProjectSpecificationDocument.model_validate_json(content)
        except ValidationError as exception:
            raise AppException(ErrorCode.PROJECT_SPECIFICATION_BUILD_FAILED) from exception
        if document.project_id != project_id:
            raise AppException(ErrorCode.PROJECT_SPECIFICATION_BUILD_FAILED)
        return document

    async def _write(self, location, document: ProjectSpecificationDocument) -> None:
        content = json.dumps(
            document.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
        ).encode("utf-8")
        await asyncio.to_thread(
            self._storage.put_bytes,
            location,
            content,
            "application/json",
        )

    def _build_prompt(
        self,
        project,
        existing: ProjectSpecificationDocument | None,
        sources: list[dict[str, Any]],
        source_paths: list[str],
    ) -> str:
        existing_json = (
            existing.model_dump_json(indent=2)
            if existing is not None
            else "null"
        )
        source_json = json.dumps(sources, ensure_ascii=False, indent=2)
        source_meta = json.dumps(
            {
                "project_id": project.id,
                "project_name": project.project_name,
                "source_selection": "按重要度截取的当前有效文件分析投影",
                "source_inventory_is_complete": True,
                "current_source_paths": source_paths,
            },
            ensure_ascii=False,
            indent=2,
        )
        return (
            f"{ProjectSpecificationPrompt.PROJECT_SPECIFICATION.value}"
            f"\n\n# 实际输入\nexisting_specification_json：\n{existing_json}"
            f"\n\nnew_content（当前有效文件分析投影）：\n{source_json}"
            f"\n\nsource_meta：\n{source_meta}"
            "\n\n# 最终约束\n"
            f"project_id 必须为整数 {project.id}。"
            "不得仅因本次分析投影未出现某个来源就删除或废弃旧规则；"
            "只有规则引用的非空 path 不在完整 current_source_paths 中时，"
            "才可基于来源删除将其标记为 deprecated 或 pending_review。"
        )

    def _build_sources(self, files: Iterable[Any]) -> list[dict[str, Any]]:
        eligible = [
            file
            for file in files
            if file.business_code == "project"
            and file.status == "active"
            and file.upload_status == "success"
            and file.analysis_version
            and file.summary
        ]
        priority = {"high": 0, "medium": 1, "low": 2, None: 3}
        eligible.sort(
            key=lambda file: (
                priority.get(file.importance, 3),
                file.relative_path,
            )
        )
        return [
            {
                "file_id": file.id,
                "path": file.relative_path,
                "module": file.module,
                "kind": file.kind,
                "language": file.language,
                "importance": file.importance,
                "summary": file.summary[:300],
                "keywords": (file.keywords or [])[:10],
                "detail_ref": file.detail_ref,
            }
            for file in eligible[: self.MAX_SOURCE_FILES]
        ]

    @staticmethod
    def _build_source_paths(files: Iterable[Any]) -> list[str]:
        return sorted(
            file.relative_path
            for file in files
            if file.business_code == "project"
            and file.status == "active"
            and file.upload_status == "success"
        )

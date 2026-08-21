"""项目文件分析与上下文发布编排服务。"""

from __future__ import annotations

import asyncio
import json

from app.core.errors import AppException, ErrorCode
from app.core.logger import get_logger
from app.infrastructure.storage import (
    ObjectStorage,
    StorageLocationFactory,
)
from app.modules.project.service import ProjectService
from app.modules.project_file.analysis.schemas import (
    ProjectFileAnalysisBatchResult,
    ProjectFileAnalysisFailure,
)
from app.modules.project_file.models import ProjectFile
from app.modules.project_file.repository import ProjectFileRepository
from app.project_context.file_detail.schemas import (
    FileSemanticAnalysisRequest,
    FileSemanticAnalysisResult,
)
from app.project_context.file_detail.extraction import (
    FileContentExtractionService,
)
from app.project_context.file_detail.service import FileSemanticAnalysisService
from app.project_context.index import ProjectIndexService
from app.project_context.specification import ProjectSpecificationService

logger = get_logger(__name__)


class ProjectFileAnalysisService:
    """编排源文件读取、内容提取、语义分析、详情发布和上下文刷新。"""

    def __init__(
        self,
        repository: ProjectFileRepository,
        projects: ProjectService,
        storage: ObjectStorage,
        locations: StorageLocationFactory,
        index_service: ProjectIndexService,
        content_extractor: FileContentExtractionService,
        semantic_analyzer: FileSemanticAnalysisService,
        specification_service: ProjectSpecificationService,
    ) -> None:
        self._repository = repository
        self._projects = projects
        self._storage = storage
        self._locations = locations
        self._index = index_service
        self._content_extractor = content_extractor
        self._semantic_analyzer = semantic_analyzer
        self._specification = specification_service

    async def analyze_pending_files(
        self,
        user_id: int,
        project_id: int,
        *,
        force: bool = False,
    ) -> ProjectFileAnalysisBatchResult:
        project = await self._projects.require_owned(user_id, project_id)
        candidates = await self._repository.list_analysis_candidates(
            project_id,
            force=force,
        )
        await self._repository.session.commit()
        logger.info(
            "开始分析项目文件 action=project_file.analysis.batch "
            "userId=%s projectId=%s force=%s candidateCount=%s",
            user_id,
            project_id,
            force,
            len(candidates),
        )

        success_count = 0
        failure_count = 0
        failures: list[ProjectFileAnalysisFailure] = []
        for file in candidates:
            request = self._build_request(project.owner_user_id, file)
            result = await self._analyze_file(file, request)
            if result.status == "success" and result.detail is not None:
                result = await self._write_detail_or_failure(
                    project.owner_user_id,
                    project.id,
                    result,
                )
            if result.status == "success" and result.detail is not None:
                updated = await self._repository.record_analysis_success(
                    project_id,
                    file.id,
                    file.content_hash,
                    file.lock_version,
                    result.detail,
                )
            else:
                updated = await self._repository.record_analysis_failure(
                    project_id,
                    file.id,
                    file.content_hash,
                    file.lock_version,
                    result.error_code or "FILE_DETAIL_ANALYSIS_FAILED",
                    result.error_message or "文件分析失败",
                )
            if not updated:
                await self._repository.session.rollback()
                logger.error(
                    "文件分析结果落库冲突 action=project_file.analysis.batch "
                    "userId=%s projectId=%s fileId=%s",
                    user_id,
                    project_id,
                    file.id,
                )
                raise AppException(
                    ErrorCode.SYSTEM_ERROR,
                    "文件分析结果落库失败，文件可能已发生变化",
                )
            await self._repository.session.commit()
            if result.status == "success":
                success_count += 1
                logger.info(
                    "文件语义分析成功 action=project_file.semantic.analyze "
                    "userId=%s projectId=%s fileId=%s",
                    user_id,
                    project_id,
                    file.id,
                )
            else:
                failure_count += 1
                failures.append(
                    ProjectFileAnalysisFailure(
                        file_id=file.id,
                        relative_path=file.relative_path,
                        error_code=(result.error_code or "FILE_DETAIL_ANALYSIS_FAILED"),
                        error_message=result.error_message or "文件分析失败",
                    )
                )
                logger.warning(
                    "文件分析失败 action=project_file.analysis.batch "
                    "userId=%s projectId=%s fileId=%s errorCode=%s",
                    user_id,
                    project_id,
                    file.id,
                    result.error_code or "FILE_DETAIL_ANALYSIS_FAILED",
                )

        files = await self._repository.list(project_id, include_system=True)
        await self._repository.session.commit()
        specification_status = "updated"
        try:
            specification_status = await self._specification.refresh(project, files)
        except Exception:
            specification_status = "failed"
            logger.exception(
                "项目规范刷新失败，保留原有规范 "
                "action=project_file.analysis.batch "
                "userId=%s projectId=%s",
                user_id,
                project_id,
            )
        index_status = "updated"
        try:
            await self._index.write(project, files)
        except Exception:
            index_status = "failed"
            logger.exception(
                "项目索引发布失败 action=project_file.analysis.batch "
                "userId=%s projectId=%s",
                user_id,
                project_id,
            )
        status = (
            "partial"
            if failure_count
            or specification_status == "failed"
            or index_status == "failed"
            else "success"
        )
        logger.info(
            "项目文件分析完成 action=project_file.analysis.batch "
            "userId=%s projectId=%s successCount=%s failureCount=%s",
            user_id,
            project_id,
            success_count,
            failure_count,
        )
        return ProjectFileAnalysisBatchResult(
            status=status,
            candidate_count=len(candidates),
            success_count=success_count,
            failure_count=failure_count,
            failures=failures,
            specification_status=specification_status,
            index_status=index_status,
        )

    async def _analyze_file(
        self,
        file: ProjectFile,
        request: FileSemanticAnalysisRequest,
    ) -> FileSemanticAnalysisResult:
        """读取指定文件快照，提取标准文本并执行语义分析。"""
        try:
            source_bytes = await asyncio.to_thread(
                self._storage.read_bytes,
                self._locations.existing_object(
                    request.user_id,
                    file.project_id,
                    file.object_key,
                ),
            )
        except AppException as exception:
            logger.warning(
                "源文件读取失败 action=project_file.source.read "
                "projectId=%s fileId=%s errorCode=%s",
                file.project_id,
                file.id,
                exception.error.name,
            )
            return FileSemanticAnalysisResult(
                project_id=file.project_id,
                file_id=file.id,
                content_hash=file.content_hash,
                status="failed",
                error_code=exception.error.name,
                error_message=exception.message,
            )
        try:
            extracted_content = await self._content_extractor.extract_from_bytes(
                source_bytes,
                request.file_type,
                request.filename,
            )
        except Exception:
            logger.exception(
                "文件内容提取失败 action=project_file.content.extract "
                "projectId=%s fileId=%s",
                file.project_id,
                file.id,
            )
            return FileSemanticAnalysisResult(
                project_id=file.project_id,
                file_id=file.id,
                content_hash=file.content_hash,
                status="failed",
                error_code="FILE_DETAIL_ANALYSIS_FAILED",
                error_message="文件内容提取失败",
            )
        try:
            return await self._semantic_analyzer.analyze(request, extracted_content)
        except Exception:
            logger.exception(
                "文件语义分析器执行失败 action=project_file.semantic.analyze "
                "projectId=%s fileId=%s",
                file.project_id,
                file.id,
            )
            return FileSemanticAnalysisResult(
                project_id=file.project_id,
                file_id=file.id,
                content_hash=file.content_hash,
                status="failed",
                error_code="FILE_DETAIL_ANALYSIS_FAILED",
                error_message="文件语义分析器执行失败",
            )

    async def _write_detail(
        self,
        user_id: int,
        project_id: int,
        result: FileSemanticAnalysisResult,
    ) -> None:
        """将服务端组装的文件详情写入 system 区域。"""
        detail = result.detail
        if detail is None:
            raise AppException(ErrorCode.FILE_ANALYSIS_FAILED)
        location = self._locations.system_file(
            user_id,
            project_id,
            detail.detail_ref.removeprefix("system/"),
        )
        await asyncio.to_thread(
            self._storage.put_bytes,
            location,
            json.dumps(
                detail.model_dump(mode="json"),
                ensure_ascii=False,
                indent=2,
            ).encode("utf-8"),
            "application/json",
        )
        logger.debug(
            "文件详情写入完成 action=project_file.detail.write projectId=%s fileId=%s",
            project_id,
            result.file_id,
        )

    async def _write_detail_or_failure(
        self,
        user_id: int,
        project_id: int,
        result: FileSemanticAnalysisResult,
    ) -> FileSemanticAnalysisResult:
        try:
            await self._write_detail(user_id, project_id, result)
            return result
        except AppException as exception:
            error_code = exception.error.name
            error_message = exception.message
            logger.warning(
                "文件详情写入失败 action=project_file.detail.write "
                "projectId=%s fileId=%s errorCode=%s",
                project_id,
                result.file_id,
                error_code,
            )
        except Exception:
            error_code = "FILE_DETAIL_WRITE_FAILED"
            error_message = "文件详情写入失败"
            logger.exception(
                "文件详情写入失败 action=project_file.detail.write "
                "projectId=%s fileId=%s errorCode=%s",
                project_id,
                result.file_id,
                error_code,
            )
        return FileSemanticAnalysisResult(
            project_id=result.project_id,
            file_id=result.file_id,
            content_hash=result.content_hash,
            status="failed",
            error_code=error_code,
            error_message=error_message,
        )

    def _build_request(
        self,
        user_id: int,
        file: ProjectFile,
    ) -> FileSemanticAnalysisRequest:
        """构建包含当前文件快照身份的分析请求。"""
        detail_ref = (
            f"system/file_details/{file.storage_uuid}-"
            f"{file.content_hash}-{file.path_hash}.json"
        )
        return FileSemanticAnalysisRequest(
            user_id=user_id,
            project_id=file.project_id,
            business=file.business_code,
            file_id=file.id,
            filename=file.file_name,
            file_url="",
            file_type=file.extension or file.content_type,
            storage_uuid=file.storage_uuid,
            storage_name=file.storage_name,
            detail_ref=detail_ref,
            original_path=file.relative_path,
            minio_path=file.minio_path,
            size_bytes=file.size_bytes,
            content_type=file.content_type,
            content_hash=file.content_hash,
        )

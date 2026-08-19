"""项目文件解析编排服务。"""

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
from app.project.context.detail_analysis.schemas import (
    FileAnalysisRequest,
    FileAnalysisResult,
)
from app.project.context.detail_analysis.service import FileDetailAnalysisService
from app.project.context.index import ProjectIndexService
from app.project.context.specification import ProjectSpecificationService

logger = get_logger(__name__)


class ProjectFileAnalysisService:
    """在 Python 进程内完成读取、解析、落库和索引重建。"""

    ANALYSIS_VERSION = "file-detail-v1.0"

    def __init__(
        self,
        repository: ProjectFileRepository,
        projects: ProjectService,
        storage: ObjectStorage,
        locations: StorageLocationFactory,
        index_service: ProjectIndexService,
        analyzer: FileDetailAnalysisService,
        specification_service: ProjectSpecificationService,
    ) -> None:
        self._repository = repository
        self._projects = projects
        self._storage = storage
        self._locations = locations
        self._index = index_service
        self._analyzer = analyzer
        self._specification = specification_service

    async def initialize(
        self,
        user_id: int,
        project_id: int,
    ) -> ProjectFileAnalysisBatchResult:
        project = await self._projects.require_owned(user_id, project_id)
        candidates = await self._repository.list_parse_candidates(
            project_id,
            self.ANALYSIS_VERSION,
        )
        await self._repository.session.commit()
        logger.info(
            "开始解析项目文件 action=project_file.analyze "
            "userId=%s projectId=%s candidateCount=%s",
            user_id,
            project_id,
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
                    result.detail,
                )
            else:
                updated = await self._repository.record_analysis_failure(
                    project_id,
                    file.id,
                    file.content_hash,
                    result.error_code or "FILE_DETAIL_ANALYSIS_FAILED",
                    result.error_message or "文件解析失败",
                )
            if not updated:
                await self._repository.session.rollback()
                logger.error(
                    "文件分析结果落库冲突 action=project_file.analyze "
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
                    "文件解析成功 action=project_file.analyze "
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
                        error_message=result.error_message or "文件解析失败",
                    )
                )
                logger.warning(
                    "文件解析失败 action=project_file.analyze "
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
                "项目规范刷新失败，保留原有规范 action=project_file.analyze "
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
                "项目索引发布失败 action=project_file.analyze userId=%s projectId=%s",
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
            "项目文件解析完成 action=project_file.analyze "
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
        request: FileAnalysisRequest,
    ) -> FileAnalysisResult:
        """读取文件内容并且解析"""
        try:
            content = await asyncio.to_thread(
                self._storage.get_bytes,
                self._locations.existing_object(
                    request.user_id,
                    file.project_id,
                    file.object_key,
                ),
            )
        except AppException as exception:
            logger.warning(
                "读取待解析文件失败 action=project_file.analyze "
                "projectId=%s fileId=%s errorCode=%s",
                file.project_id,
                file.id,
                exception.error.name,
            )
            return FileAnalysisResult(
                project_id=file.project_id,
                file_id=file.id,
                content_hash=file.content_hash,
                analysis_version=self.ANALYSIS_VERSION,
                status="failed",
                error_code=exception.error.name,
                error_message=exception.message,
            )
        try:
            return await self._analyzer.analyze_bytes(request, content)
        except Exception:
            logger.exception(
                "文件分析器执行失败 action=project_file.analyze projectId=%s fileId=%s",
                file.project_id,
                file.id,
            )
            return FileAnalysisResult(
                project_id=file.project_id,
                file_id=file.id,
                content_hash=file.content_hash,
                analysis_version=self.ANALYSIS_VERSION,
                status="failed",
                error_code="FILE_DETAIL_ANALYSIS_FAILED",
                error_message="文件分析器执行失败",
            )

    async def _write_detail(
        self,
        user_id: int,
        project_id: int,
        result: FileAnalysisResult,
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
            "文件分析详情写入完成 action=project_file.analyze.detail "
            "projectId=%s fileId=%s",
            project_id,
            result.file_id,
        )

    async def _write_detail_or_failure(
        self,
        user_id: int,
        project_id: int,
        result: FileAnalysisResult,
    ) -> FileAnalysisResult:
        try:
            await self._write_detail(user_id, project_id, result)
            return result
        except AppException as exception:
            error_code = exception.error.name
            error_message = exception.message
            logger.warning(
                "文件详情写入失败 action=project_file.analyze.detail "
                "projectId=%s fileId=%s errorCode=%s",
                project_id,
                result.file_id,
                error_code,
            )
        except Exception:
            error_code = "FILE_DETAIL_WRITE_FAILED"
            error_message = "文件详情写入失败"
            logger.exception(
                "文件详情写入失败 action=project_file.analyze.detail "
                "projectId=%s fileId=%s errorCode=%s",
                project_id,
                result.file_id,
                error_code,
            )
        return FileAnalysisResult(
            project_id=result.project_id,
            file_id=result.file_id,
            content_hash=result.content_hash,
            analysis_version=result.analysis_version,
            status="failed",
            error_code=error_code,
            error_message=error_message,
        )

    def _build_request(
        self,
        user_id: int,
        file: ProjectFile,
    ) -> FileAnalysisRequest:
        """构建包含当前文件版本身份的分析请求。"""
        detail_name = (
            file.storage_name.rsplit(".", maxsplit=1)[0]
            if "." in file.storage_name
            else file.storage_name
        )
        detail_ref = (
            f"system/file_details/{detail_name}-"
            f"{file.content_hash}-{self.ANALYSIS_VERSION}.json"
        )
        return FileAnalysisRequest(
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
            analysis_version=self.ANALYSIS_VERSION,
        )

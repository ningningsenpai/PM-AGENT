"""项目文件分析服务依赖装配。"""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppException, ErrorCode
from app.infrastructure.database import get_db_session
from app.infrastructure.storage import (
    ObjectStorage,
    StorageLocationFactory,
    get_object_storage,
)
from app.llm.factory import get_llm_client
from app.llm.structured import StructuredJsonGenerator
from app.modules.chat.context.service import ContextService
from app.modules.chat.dependencies import get_context_service, get_run_service
from app.modules.chat.runs.service import RunService
from app.modules.project.dependencies import get_project_service
from app.modules.project.service import ProjectService
from app.modules.project_file.analysis.service import ProjectFileAnalysisService
from app.modules.project_file.repository import ProjectFileRepository
from app.project_context.file_detail import FileDownloader
from app.project_context.file_detail.extraction import (
    FileContentExtractionService,
    FileContentExtractorFactory,
)
from app.project_context.file_detail.service import FileSemanticAnalysisService
from app.project_context.index import ProjectIndexService
from app.project_context.specification import ProjectSpecificationService


def get_project_file_analysis_service(
    session: AsyncSession = Depends(get_db_session),
    projects: ProjectService = Depends(get_project_service),
    storage: ObjectStorage = Depends(get_object_storage),
    runs: RunService = Depends(get_run_service),
    contexts: ContextService = Depends(get_context_service),
) -> ProjectFileAnalysisService:
    """装配请求级项目文件分析服务。"""
    settings = get_settings()
    file_detail_config = settings.llm.file_detail
    if not file_detail_config.enabled:
        raise AppException(
            ErrorCode.FILE_ANALYSIS_FAILED,
            "文件语义分析模型未启用，请先配置 DeepSeek 并开启文件详情分析",
        )
    llm = get_llm_client(file_detail_config.provider, settings.llm)
    generator = StructuredJsonGenerator(
        llm,
        max_tokens=file_detail_config.max_output_tokens,
        timeout_seconds=file_detail_config.request_timeout_seconds,
    )
    locations = StorageLocationFactory(settings.storage)
    return ProjectFileAnalysisService(
        ProjectFileRepository(session),
        projects,
        storage,
        locations,
        ProjectIndexService(storage, locations),
        FileContentExtractionService(
            FileDownloader(),
            FileContentExtractorFactory(),
        ),
        FileSemanticAnalysisService(
            generator,
            max_semantic_input_bytes=file_detail_config.max_semantic_input_bytes,
        ),
        ProjectSpecificationService(storage, locations, generator, contexts=contexts),
        runs=runs,
    )

"""报告业务依赖装配，共享请求级数据库会话。"""

from fastapi import Depends

from app.core.config import get_settings
from app.infrastructure.database import get_db_session
from app.llm.dependencies import get_structured_generator
from app.modules.chat.dependencies import get_context_service, get_run_service
from app.modules.project.dependencies import get_project_service
from app.modules.project_file.management.dependencies import get_project_file_service

from .repository import ReportRepository
from .service import ReportService


def get_report_service(
    session=Depends(get_db_session),
    projects=Depends(get_project_service),
    files=Depends(get_project_file_service),
    contexts=Depends(get_context_service),
    runs=Depends(get_run_service),
):
    return ReportService(
        ReportRepository(session),
        projects,
        files,
        contexts,
        runs,
        get_structured_generator(get_settings().llm.report_max_tokens),
    )

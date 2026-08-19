"""项目文件路由聚合。"""

from fastapi import APIRouter

from app.modules.project_file.analysis.api import router as analysis_router
from app.modules.project_file.management.api import router as management_router
from app.modules.project_file.sync.api import router as sync_router

PROJECT_FILE_API_PREFIX = "/api/v1/projects/{project_id}/files"

router = APIRouter()
router.include_router(
    sync_router,
    prefix=PROJECT_FILE_API_PREFIX,
    tags=["项目文件"],
)
router.include_router(
    management_router,
    prefix=PROJECT_FILE_API_PREFIX,
    tags=["项目文件"],
)
router.include_router(
    analysis_router,
    prefix=PROJECT_FILE_API_PREFIX,
    tags=["项目文件"],
)

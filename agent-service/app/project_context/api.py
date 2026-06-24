from fastapi import APIRouter, Header

from app.core.logger import get_logger
from app.project_context.schemas import ProjectInitRequest

router = APIRouter(prefix="/api/v1/context", tags=["Project Context"])
logger = get_logger(__name__)

@router.post("/initProject")
async def initProject(
    request: ProjectInitRequest,
    x_trace_id: str | None = Header(default=None, alias="X-Trace-Id"),
    x_user_id: int | None = Header(default=None, alias="X-User-Id"),
    x_tenant_id: int | None = Header(default=None, alias="X-Tenant-Id"),
    # x_trace_id: int = Header(..., alias="X-Trace-Id"),
    # x_user_id: int = Header(..., alias="X-User-Id"),
    # x_tenant_id: int = Header(..., alias="X-Tenant-Id"),
):
    """初始化项目上下文请求。"""
    


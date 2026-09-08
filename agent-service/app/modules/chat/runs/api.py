"""当前用户项目的运行结果与轨迹查询接口。"""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.identifiers import SnowflakeId
from app.core.response import success
from app.core.security import AuthPrincipal, require_principal

from ..dependencies import get_run_service

router = APIRouter(prefix="/api/v1/agent", tags=["项目助手闭环"])
Principal = Annotated[AuthPrincipal, Depends(require_principal)]


@router.get("/runs/{run_id}")
async def get_run(
    run_id: SnowflakeId, principal: Principal, service=Depends(get_run_service)
):
    return success(await service.get(principal.user_id, run_id))

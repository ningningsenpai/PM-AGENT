"""项目报告的显式生成与读取接口。"""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header

from app.core.identifiers import SnowflakeId
from app.core.response import success
from app.core.security import AuthPrincipal, require_principal
from app.core.trace import get_trace_id
from app.modules.chat.dependencies import get_report_service
from app.modules.chat.schemas import GenerateReport

router = APIRouter(prefix="/api/v1/projects/{project_id}/reports", tags=["项目报告"])


@router.post("")
async def generate_report(
    project_id: SnowflakeId,
    request: GenerateReport,
    principal: Annotated[AuthPrincipal, Depends(require_principal)],
    idempotency_key: Annotated[str | None, Header(alias="X-Idempotency-Key")] = None,
    service=Depends(get_report_service),
):
    return success(
        await service.generate(
            principal.user_id, project_id, request, idempotency_key, get_trace_id()
        )
    )


@router.get("")
async def list_reports(
    project_id: SnowflakeId,
    principal: Annotated[AuthPrincipal, Depends(require_principal)],
    kind: Literal["development", "risk"] | None = None,
    service=Depends(get_report_service),
):
    return success(await service.list(principal.user_id, project_id, kind))


@router.get("/{report_id}")
async def get_report(
    project_id: SnowflakeId,
    report_id: SnowflakeId,
    principal: Annotated[AuthPrincipal, Depends(require_principal)],
    service=Depends(get_report_service),
):
    return success(
        await service.list(principal.user_id, project_id, report_id=report_id)
    )

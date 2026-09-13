"""项目上下文的查询、纠正与快照重发接口。"""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query

from app.core.identifiers import SnowflakeId
from app.core.response import success
from app.core.security import AuthPrincipal, require_principal

from ..dependencies import get_context_service
from .schemas import UpdateEntry

router = APIRouter(prefix="/api/v1/agent", tags=["项目助手闭环"])
Principal = Annotated[AuthPrincipal, Depends(require_principal)]


@router.get("/context-entries")
async def list_entries(
    principal: Principal,
    project_id: Annotated[SnowflakeId, Query(alias="projectId")],
    effective: bool = True,
    service=Depends(get_context_service),
):
    return success(
        await service.list_entries(principal.user_id, project_id, effective=effective)
    )


@router.patch("/context-entries/{entry_id}")
async def update_entry(
    entry_id: SnowflakeId,
    request: UpdateEntry,
    principal: Principal,
    idempotency_key: Annotated[str | None, Header(alias="X-Idempotency-Key")] = None,
    service=Depends(get_context_service),
):
    return success(
        await service.update_entry(
            principal.user_id, entry_id, request, idempotency_key
        )
    )


@router.get("/context-entries/changes")
async def context_changes(
    principal: Principal,
    project_id: Annotated[SnowflakeId, Query(alias="projectId")],
    entry_id: Annotated[SnowflakeId | None, Query(alias="entryId")] = None,
    service=Depends(get_context_service),
):
    return success(await service.changes(principal.user_id, project_id, entry_id))


@router.post("/context-entries/publish")
async def publish_context(
    principal: Principal,
    project_id: Annotated[SnowflakeId, Query(alias="projectId")],
    service=Depends(get_context_service),
):
    return success(await service.publish(principal.user_id, project_id))

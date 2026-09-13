"""对话自动识别产生的待确认上下文更新接口。"""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query

from app.core.identifiers import SnowflakeId
from app.core.response import success
from app.core.security import AuthPrincipal, require_principal
from app.core.trace import get_trace_id

from ..dependencies import get_learning_service
from .schemas import ConfirmDraft, DraftVersion, EditDraft, RefineDraft

router = APIRouter(prefix="/api/v1/agent", tags=["项目助手闭环"])
Principal = Annotated[AuthPrincipal, Depends(require_principal)]
RequestKey = Annotated[str | None, Header(alias="X-Idempotency-Key")]
ProjectId = Annotated[SnowflakeId, Query(alias="projectId")]


@router.get("/learning-drafts")
async def list_drafts(
    principal: Principal,
    project_id: ProjectId,
    conversation_id: Annotated[
        SnowflakeId | None, Query(alias="conversationId")
    ] = None,
    service=Depends(get_learning_service),
):
    return success(await service.list(principal.user_id, project_id, conversation_id))


@router.get("/learning-drafts/{draft_id}")
async def get_draft(
    draft_id: SnowflakeId,
    principal: Principal,
    project_id: ProjectId,
    service=Depends(get_learning_service),
):
    return success(await service.get(principal.user_id, project_id, draft_id))


@router.patch("/learning-drafts/{draft_id}")
async def edit_draft(
    draft_id: SnowflakeId,
    request: EditDraft,
    principal: Principal,
    project_id: ProjectId,
    service=Depends(get_learning_service),
):
    return success(await service.edit(principal.user_id, project_id, draft_id, request))


@router.post("/learning-drafts/{draft_id}/refine")
async def refine_draft(
    draft_id: SnowflakeId,
    request: RefineDraft,
    principal: Principal,
    project_id: ProjectId,
    idempotency_key: RequestKey = None,
    service=Depends(get_learning_service),
):
    return success(
        await service.refine(
            principal.user_id,
            project_id,
            draft_id,
            request,
            idempotency_key,
            get_trace_id(),
        )
    )


@router.post("/learning-drafts/{draft_id}/confirm")
async def confirm_draft(
    draft_id: SnowflakeId,
    request: ConfirmDraft,
    principal: Principal,
    project_id: ProjectId,
    service=Depends(get_learning_service),
):
    return success(
        await service.confirm(principal.user_id, project_id, draft_id, request)
    )


@router.post("/learning-drafts/{draft_id}/rebase")
async def rebase_draft(
    draft_id: SnowflakeId,
    request: DraftVersion,
    principal: Principal,
    project_id: ProjectId,
    service=Depends(get_learning_service),
):
    return success(
        await service.rebase(principal.user_id, project_id, draft_id, request.version)
    )

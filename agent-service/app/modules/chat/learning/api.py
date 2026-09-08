"""用户显式触发的会话增量学习接口。"""

from typing import Annotated

from fastapi import APIRouter, Depends, Header

from app.core.identifiers import SnowflakeId
from app.core.response import success
from app.core.security import AuthPrincipal, require_principal
from app.core.trace import get_trace_id

from ..dependencies import get_learning_service

router = APIRouter(prefix="/api/v1/agent", tags=["项目助手闭环"])
Principal = Annotated[AuthPrincipal, Depends(require_principal)]
RequestKey = Annotated[str | None, Header(alias="X-Idempotency-Key")]


@router.post("/conversations/{conversation_id}/learn")
async def learn(
    conversation_id: SnowflakeId,
    principal: Principal,
    idempotency_key: RequestKey = None,
    service=Depends(get_learning_service),
):
    return success(
        await service.learn(
            principal.user_id, conversation_id, idempotency_key, get_trace_id()
        )
    )

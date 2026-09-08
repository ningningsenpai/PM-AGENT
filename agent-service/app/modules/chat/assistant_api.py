"""会话、显式学习、上下文管理与运行轨迹接口。"""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query

from app.agents.dependencies import get_project_chat_agent
from app.core.identifiers import SnowflakeId
from app.core.response import success
from app.core.security import AuthPrincipal, require_principal
from app.core.trace import get_trace_id

from .conversation_service import ConversationService
from .dependencies import (
    get_context_service,
    get_conversation_service,
    get_learning_service,
    get_run_service,
)
from .schemas import CreateConversation, RenameConversation, SendMessage, UpdateEntry

router = APIRouter(prefix="/api/v1/agent", tags=["项目助手闭环"])
Principal = Annotated[AuthPrincipal, Depends(require_principal)]
RequestKey = Annotated[str | None, Header(alias="X-Idempotency-Key")]


@router.post("/conversations")
async def create_conversation(
    request: CreateConversation,
    principal: Principal,
    service=Depends(get_conversation_service),
):
    return success(await service.create(principal.user_id, request))


@router.get("/conversations")
async def list_conversations(
    principal: Principal,
    project_id: Annotated[SnowflakeId, Query(alias="projectId")],
    service=Depends(get_conversation_service),
):
    return success(await service.list(principal.user_id, project_id))


@router.get("/conversations/{conversation_id}/messages")
async def list_messages(
    conversation_id: SnowflakeId,
    principal: Principal,
    service=Depends(get_conversation_service),
):
    return success(await service.messages(principal.user_id, conversation_id))


@router.patch("/conversations/{conversation_id}")
async def rename_conversation(
    conversation_id: SnowflakeId,
    request: RenameConversation,
    principal: Principal,
    service: Annotated[ConversationService, Depends(get_conversation_service)],
):
    return success(await service.rename(principal.user_id, conversation_id, request))


@router.post("/conversations/{conversation_id}/messages")
async def send_message(
    conversation_id: SnowflakeId,
    request: SendMessage,
    principal: Principal,
    idempotency_key: RequestKey = None,
    service=Depends(get_conversation_service),
    agent=Depends(get_project_chat_agent),
):
    return success(
        await service.send(
            principal.user_id,
            conversation_id,
            request,
            idempotency_key,
            get_trace_id(),
            agent,
        )
    )


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
    service=Depends(get_context_service),
):
    return success(await service.update_entry(principal.user_id, entry_id, request))


@router.post("/context-entries/publish")
async def publish_context(
    principal: Principal,
    project_id: Annotated[SnowflakeId, Query(alias="projectId")],
    service=Depends(get_context_service),
):
    return success(await service.publish(principal.user_id, project_id))


@router.get("/tools")
async def list_tools(
    principal: Principal,
    conversation_id: Annotated[SnowflakeId, Query(alias="conversationId")],
    conversations=Depends(get_conversation_service),
    agent=Depends(get_project_chat_agent),
):
    await conversations.owned(principal.user_id, conversation_id)
    return success({"tools": agent.tool_catalog()})


@router.get("/runs/{run_id}")
async def get_run(
    run_id: SnowflakeId, principal: Principal, service=Depends(get_run_service)
):
    return success(await service.get(principal.user_id, run_id))

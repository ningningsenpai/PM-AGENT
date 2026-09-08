"""会话管理、持久化消息与当前会话工具目录接口。"""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query

from app.agents.dependencies import get_project_chat_agent
from app.core.identifiers import SnowflakeId
from app.core.response import success
from app.core.security import AuthPrincipal, require_principal
from app.core.trace import get_trace_id

from ..conversation_service import ConversationService
from ..dependencies import get_conversation_service
from .schemas import CreateConversation, RenameConversation, SendMessage

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


@router.get("/tools")
async def list_tools(
    principal: Principal,
    conversation_id: Annotated[SnowflakeId, Query(alias="conversationId")],
    conversations=Depends(get_conversation_service),
    agent=Depends(get_project_chat_agent),
):
    await conversations.owned(principal.user_id, conversation_id)
    return success({"tools": agent.tool_catalog()})

"""Agent API。"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.core.config import get_settings
from app.core.errors import AppException, ErrorCode
from app.core.security import AuthPrincipal, require_principal
from app.llm.orchestration.project_chat_agent import ProjectChatAgent
from app.streaming import SSEFormatter, StreamEventType
from app.streaming.payloads import AgentChatRequest, ApiResponse, StreamMetaPayload

router = APIRouter(prefix="/api/v1/agent", tags=["Agent"])


@router.post("/chat")
async def chat(
    request: AgentChatRequest,
    principal: AuthPrincipal = Depends(require_principal),
):
    """项目问答接口，支持普通响应和 SSE 流式响应。"""
    if request.user.user_id != principal.user_id:
        raise AppException(ErrorCode.FORBIDDEN, "请求用户与登录用户不一致")
    settings = get_settings()
    agent = ProjectChatAgent(settings)

    if request.stream:
        async def event_generator():
            yield SSEFormatter.format(
                StreamEventType.META,
                StreamMetaPayload(
                    traceId=request.trace_id,
                    conversationId=request.conversation_id,
                    userId=request.user.user_id,
                    tenantId=request.user.tenant_id,
                ),
            )
            async for event in agent.stream_chat(request):
                yield SSEFormatter.format(event["event"], event["data"])
            yield SSEFormatter.done_marker()

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    data = await agent.chat(request)
    return ApiResponse(data=data, traceId=request.trace_id)

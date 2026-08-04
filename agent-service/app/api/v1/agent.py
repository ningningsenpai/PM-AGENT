"""Agent API。"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.agents.dependencies import get_project_chat_agent
from app.core.errors import AppException, ErrorCode
from app.core.logger import get_logger
from app.core.security import AuthPrincipal, require_principal
from app.llm.orchestration.project_chat_agent import ProjectChatAgent
from app.streaming import SSEFormatter, StreamEventType
from app.streaming.payloads import (
    AgentChatRequest,
    ApiResponse,
    StreamErrorPayload,
    StreamMetaPayload,
)

router = APIRouter(prefix="/api/v1/agent", tags=["Agent"])
logger = get_logger(__name__)


@router.post("/chat")
async def chat(
    request: AgentChatRequest,
    principal: AuthPrincipal = Depends(require_principal),
    agent: ProjectChatAgent = Depends(get_project_chat_agent),
):
    """项目问答接口，支持普通响应和 SSE 流式响应。"""
    if request.user.user_id != principal.user_id:
        raise AppException(ErrorCode.FORBIDDEN, "请求用户与登录用户不一致")
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
            try:
                async for event in agent.stream_chat(request, principal.user_id):
                    yield SSEFormatter.format(event["event"], event["data"])
            except AppException as exception:
                yield SSEFormatter.format(
                    StreamEventType.ERROR,
                    StreamErrorPayload(
                        code=exception.error.code,
                        message=exception.message,
                        traceId=request.trace_id,
                    ),
                )
            except Exception:
                logger.exception(
                    "Agent 流式响应异常 action=agent.chat.stream userId=%s",
                    principal.user_id,
                )
                yield SSEFormatter.format(
                    StreamEventType.ERROR,
                    StreamErrorPayload(
                        code=ErrorCode.SYSTEM_ERROR.code,
                        message=ErrorCode.SYSTEM_ERROR.message,
                        traceId=request.trace_id,
                    ),
                )
            yield SSEFormatter.done_marker()

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    data = await agent.chat(request, principal.user_id)
    return ApiResponse(data=data, traceId=request.trace_id)

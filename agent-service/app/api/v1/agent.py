from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse

from app.agents.project_chat_agent import ProjectChatAgent
from app.core.config import get_settings
from app.core.logger import get_logger
from app.streaming import SSEFormatter, StreamEventType
from app.streaming.payloads import AgentChatRequest, ApiResponse, StreamMetaPayload

router = APIRouter(prefix="/api/v1/agent", tags=["Agent"])
logger = get_logger(__name__)

# TODO 完整链路测试时将 x_trace_id, x_user_id, x_tenant_id 修改为强校验
@router.post("/chat")
async def chat(
    request: AgentChatRequest,
    x_trace_id: str | None = Header(default=None, alias="X-Trace-Id"),
    x_user_id: int | None = Header(default=None, alias="X-User-Id"),
    # x_tenant_id: int | None = Header(default=None, alias="X-Tenant-Id"),
    # x_trace_id: int = Header(..., alias="X-Trace-Id"),
    # x_user_id: int = Header(..., alias="X-User-Id"),
    # x_tenant_id: int = Header(..., alias="X-Tenant-Id"),
):
    trace_id = x_trace_id or uuid4().hex
    # trace_id = x_trace_id

    # if x_user_id is not request.user.user_id:
    #     raise HTTPException(ErrorCode.UNAUTHORIZED, detail=get_error_message(ErrorCode.UNAUTHORIZED))

    settings = get_settings()
    agent = ProjectChatAgent(settings)

    if request.stream:
        async def event_generator():
            yield SSEFormatter.format(
                StreamEventType.META,
                StreamMetaPayload(
                    traceId=trace_id,
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
    return ApiResponse(data=data, traceId=trace_id)

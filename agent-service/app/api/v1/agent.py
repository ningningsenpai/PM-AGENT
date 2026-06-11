from uuid import uuid4

from fastapi import APIRouter, Header
from fastapi.responses import StreamingResponse

from app.agents.project_chat_agent import ProjectChatAgent
from app.core.config import get_settings
from app.schemas.chat import ApiResponse, ChatRequest
from app.streaming import SSEFormatter, StreamEventType

router = APIRouter(prefix="/api/v1/agent", tags=["Agent"])


@router.post("/chat")
async def chat(
    request: ChatRequest,
    x_trace_id: str | None = Header(default=None, alias="X-Trace-Id"),
    x_user_id: str | None = Header(default="0", alias="X-User-Id"),
    x_tenant_id: str | None = Header(default="0", alias="X-Tenant-Id"),
):
    """Agent 对话；支持普通 JSON 和 SSE 流式输出。"""
    trace_id = x_trace_id or uuid4().hex
    settings = get_settings()
    agent = ProjectChatAgent(settings)

    if request.stream:
        async def event_generator():
            yield SSEFormatter.format(
                StreamEventType.META,
                {"traceId": trace_id, "userId": x_user_id, "tenantId": x_tenant_id},
            )
            async for event in agent.stream_chat(request):
                yield SSEFormatter.format(event["event"], event["data"])
            yield SSEFormatter.done_marker()

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    data = await agent.chat(request)
    return ApiResponse(data=data, traceId=trace_id)

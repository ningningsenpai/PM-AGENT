from uuid import uuid4
from fastapi import APIRouter, Header
from fastapi.responses import StreamingResponse
from app.agents.project_chat_agent import ProjectChatAgent
from app.core.config import get_settings
from app.schemas.chat import ApiResponse
from app.streaming import SSEFormatter, StreamEventType
from app.streaming.payloads import AgentChatRequest

router = APIRouter(prefix="/api/v1/agent", tags=["Agent"])


@router.post("/chat")
async def chat(
    request: AgentChatRequest,
    x_trace_id: str | None = Header(default=None, alias="X-Trace-Id"),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
):
    """Agent 对话；支持多轮对话历史、普通 JSON 与 SSE 流式输出。"""
    trace_id = x_trace_id or uuid4().hex

    # Header 中的身份字段优先级最高，便于网关在 token 校验后强制覆盖。
    if x_user_id:
        request.user.user_id = x_user_id
    if x_tenant_id:
        request.user.tenant_id = x_tenant_id

    # 没有 conversation_id 视为新会话，统一在这里生成，方便后续落库与续聊。
    if not request.conversation_id:
        request.conversation_id = uuid4().hex

    settings = get_settings()
    agent = ProjectChatAgent(settings)

    if request.stream:
        async def event_generator():
            yield SSEFormatter.format(
                StreamEventType.META,
                {
                    "traceId": trace_id,
                    "conversationId": request.conversation_id,
                    "userId": request.user.user_id,
                    "tenantId": request.user.tenant_id,
                },
            )
            async for event in agent.stream_chat(request):
                yield SSEFormatter.format(event["event"], event["data"])
            yield SSEFormatter.done_marker()

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    data = await agent.chat(request)
    return ApiResponse(data=data, traceId=trace_id)

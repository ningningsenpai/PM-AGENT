"""旧无状态问答接口；持久化问答使用 conversation 子包。"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.agents.dependencies import get_project_chat_agent
from app.core.errors import AppException, ErrorCode
from app.core.logger import get_logger
from app.core.security import AuthPrincipal, require_principal
from app.llm.orchestration.project_chat_agent import ProjectChatAgent
from app.streaming.payloads import AgentChatRequest, ApiResponse

router = APIRouter(prefix="/api/v1/agent", tags=["Agent"])
logger = get_logger(__name__)

# 旧接口保留无状态问答兼容；持久化历史和显式学习使用 conversations 系列接口。


@router.post("/chat")
async def chat(
    request: AgentChatRequest,
    principal: AuthPrincipal = Depends(require_principal),
    agent: ProjectChatAgent = Depends(get_project_chat_agent),
):
    """
    项目问答接口，目前仅支持普通响应。
    SSE 流式响应等待后续业务流程完善之后再考虑补全。
    """
    logger.info(
        "收到用户：%s 的项目问答请求：%s", request.user.user_id, request.trace_id
    )
    if request.user.user_id != principal.user_id:
        raise AppException(ErrorCode.FORBIDDEN, "请求用户与登录用户不一致")
    data = await agent.chat(request, principal.user_id)
    logger.info("项目问答响应：%s", request.trace_id)
    return ApiResponse(data=data, traceId=request.trace_id)

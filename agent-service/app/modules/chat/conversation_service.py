"""持久化会话及服务端可信的工具协议历史。"""

from __future__ import annotations

import logging
import asyncio

from app.core.errors import AppException, ErrorCode
from app.llm.telemetry import capture_calls
from app.project_context.file_detail.sensitive_content import sanitize_sensitive_content
from app.streaming.payloads import AgentChatRequest

from .models import AgentConversation, AgentMessage
from .run_service import next_id
from .schemas import ConversationView, MessageView


class ConversationService:
    def __init__(self, repository, projects, runs, contexts):
        self.repo, self.projects, self.runs, self.contexts = (
            repository,
            projects,
            runs,
            contexts,
        )

    async def owned(self, user_id, conversation_id):
        row = await self.repo.conversation(user_id, conversation_id)
        if row is None:
            raise AppException(ErrorCode.FORBIDDEN, "会话不存在或无权访问")
        await self.projects.get_owned(user_id, row.project_id)
        return row

    async def create(self, user_id, request):
        await self.projects.get_owned(user_id, request.project_id)
        # 创建会话时初始化两个作用域，后续抽取阶段只进行增量版本更新。
        await self.contexts.scopes(user_id, request.project_id)
        row = await self.repo.add(
            AgentConversation(
                id=next_id(),
                user_id=user_id,
                project_id=request.project_id,
                title=request.title,
                learned_message_id=0,
            )
        )
        view = ConversationView.model_validate(row)
        await self.repo.session.commit()
        return view

    async def list(self, user_id, project_id):
        await self.projects.get_owned(user_id, project_id)
        result = [
            ConversationView.model_validate(row)
            for row in await self.repo.conversations(user_id, project_id)
        ]
        await self.repo.session.commit()
        return result

    async def messages(self, user_id, conversation_id):
        await self.owned(user_id, conversation_id)
        result = [
            MessageView.model_validate(row)
            for row in await self.repo.messages(conversation_id)
        ]
        await self.repo.session.commit()
        return result

    async def send(self, user_id, conversation_id, request, key, trace_id, agent):
        conversation = await self.owned(user_id, conversation_id)
        run, fresh = await self.runs.start(
            user_id,
            conversation.project_id,
            "chat",
            key,
            request.model_dump(),
            trace_id,
            conversation_id,
        )
        if not fresh:
            return self.runs.view(run)
        events, protocol = [], []
        run_id, project_id = run.id, conversation.project_id
        try:
            content = sanitize_sensitive_content(request.content).text
            previous = await self.repo.messages(conversation_id)
            # 仅保留完整问答组，不拆开 assistant.tool_calls 与 tool 结果。
            history = []
            for message in previous:
                if message.role == "assistant" and message.protocol:
                    history.append(message.protocol)
            history = [item for group in history[-5:] for item in group]
            user_message = await self.repo.add(
                AgentMessage(
                    id=next_id(),
                    conversation_id=conversation_id,
                    role="user",
                    content=content,
                    run_id=run_id,
                    protocol=[],
                )
            )
            message_id = user_message.id
            await self.repo.session.commit()
            internal = AgentChatRequest(
                trace_id=trace_id,
                conversation_id=conversation_id,
                messages=[{"role": "user", "content": content}],
                context={"project_id": project_id, "context_total_usage": 0},
                user={"user_id": user_id, "user_name": "当前用户"},
            )
            with capture_calls(events):
                answer = await agent.chat(
                    internal, user_id, history=history, protocol_out=protocol
                )
            assistant_message = await self.repo.add(
                AgentMessage(
                    id=next_id(),
                    conversation_id=conversation_id,
                    role="assistant",
                    content=answer.answer,
                    run_id=run_id,
                    protocol=protocol,
                )
            )
            return await self.runs.finish(
                run_id,
                user_id,
                events,
                {
                    "messageId": str(assistant_message.id),
                    "userMessageId": str(message_id),
                    "conversationId": str(conversation_id),
                    "answer": answer.answer,
                    "model": answer.model,
                    "toolCalls": [
                        record.model_dump(mode="json") for record in answer.tool_calls
                    ],
                    "usage": answer.usage.model_dump(mode="json")
                    if answer.usage
                    else None,
                },
            )
        except asyncio.CancelledError:
            await self.runs.cancel(run_id, user_id, events)
            raise
        except Exception as exc:
            logging.getLogger(__name__).exception(
                "上下文业务运行失败，保留当前调用记录"
            )
            await self.repo.session.rollback()
            error = (
                exc.message
                if isinstance(exc, AppException)
                else f"问答失败：{type(exc).__name__}"
            )
            return await self.runs.finish(run_id, user_id, events, error=error)

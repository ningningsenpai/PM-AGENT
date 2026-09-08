"""ConversationRepository 仅执行数据库操作，不调用其他仓储或外部服务。"""

from sqlalchemy import select

from .._persistence import ChatRepositoryBase
from ..runs.models import AgentRun
from .models import AgentConversation, AgentMessage


class ConversationRepository(ChatRepositoryBase):
    async def conversation(self, user_id, conversation_id, *, lock=False):
        query = select(AgentConversation).where(
            AgentConversation.id == conversation_id,
            AgentConversation.user_id == user_id,
        )
        if lock:
            query = query.with_for_update().execution_options(populate_existing=True)
        return await self.session.scalar(query)

    async def conversations(self, user_id, project_id):
        return list(
            (
                await self.session.scalars(
                    select(AgentConversation)
                    .where(
                        AgentConversation.user_id == user_id,
                        AgentConversation.project_id == project_id,
                    )
                    .order_by(AgentConversation.id.desc())
                )
            ).all()
        )

    async def conversation_titles(self, user_id, project_id):
        return list(
            (
                await self.session.scalars(
                    select(AgentConversation.title)
                    .where(
                        AgentConversation.user_id == user_id,
                        AgentConversation.project_id == project_id,
                    )
                    .with_for_update()
                )
            ).all()
        )

    async def message_history(self, conversation_id):
        return (
            await self.session.execute(
                select(AgentMessage, AgentRun.request_key)
                .outerjoin(AgentRun, AgentRun.id == AgentMessage.run_id)
                .where(AgentMessage.conversation_id == conversation_id)
                .order_by(AgentMessage.id)
            )
        ).all()

    async def messages(self, conversation_id, *, after=0):
        return list(
            (
                await self.session.scalars(
                    select(AgentMessage)
                    .where(
                        AgentMessage.conversation_id == conversation_id,
                        AgentMessage.id > after,
                    )
                    .order_by(AgentMessage.id)
                )
            ).all()
        )

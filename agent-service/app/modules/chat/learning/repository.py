"""显式学习草稿仓储；仅负责 MySQL 读写。"""

from sqlalchemy import select

from .._persistence import ChatRepositoryBase
from .models import AgentLearningDraft


class LearningDraftRepository(ChatRepositoryBase):
    async def get(self, user_id, project_id, draft_id, *, lock=False):
        statement = select(AgentLearningDraft).where(
            AgentLearningDraft.id == draft_id,
            AgentLearningDraft.user_id == user_id,
            AgentLearningDraft.project_id == project_id,
        )
        if lock:
            statement = statement.with_for_update()
        return await self.session.scalar(statement)

    async def list(self, user_id, project_id, conversation_id=None):
        statement = select(AgentLearningDraft).where(
            AgentLearningDraft.user_id == user_id,
            AgentLearningDraft.project_id == project_id,
        )
        if conversation_id is not None:
            statement = statement.where(
                AgentLearningDraft.conversation_id == conversation_id
            )
        statement = statement.order_by(AgentLearningDraft.id.desc())
        return list((await self.session.scalars(statement)).all())

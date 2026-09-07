"""会话与上下文的数据访问；不调用其他仓储或外部服务。"""

from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import (
    AgentContextChange,
    AgentContextEntry,
    AgentContextScope,
    AgentConversation,
    AgentMessage,
    AgentRun,
    ProjectReport,
)


class ChatRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, row):
        self.session.add(row)
        await self.session.flush()
        return row

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
                    .limit(100)
                )
            ).all()
        )

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

    async def run(self, user_id, run_id):
        return await self.session.scalar(
            select(AgentRun).where(AgentRun.user_id == user_id, AgentRun.id == run_id)
        )

    async def duplicate(self, user_id, operation, key):
        return await self.session.scalar(
            select(AgentRun).where(
                AgentRun.user_id == user_id,
                AgentRun.operation == operation,
                AgentRun.request_key == key,
            )
        )

    async def scope(self, key, *, lock=False):
        query = select(AgentContextScope).where(AgentContextScope.scope_key == key)
        if lock:
            query = query.with_for_update().execution_options(populate_existing=True)
        return await self.session.scalar(query)

    async def entries(self, user_id, project_id, *, effective=True):
        query = select(AgentContextEntry).where(
            AgentContextEntry.user_id == user_id,
            or_(
                AgentContextEntry.project_id == project_id,
                AgentContextEntry.project_id.is_(None),
            ),
        )
        if effective:
            query = query.where(
                AgentContextEntry.status == "active",
                or_(
                    AgentContextEntry.expires_at.is_(None),
                    AgentContextEntry.expires_at > datetime.now(UTC).replace(tzinfo=None),
                ),
            )
        return list(
            (await self.session.scalars(query.order_by(AgentContextEntry.id))).all()
        )

    async def entry(self, user_id, entry_id, *, lock=False):
        query = select(AgentContextEntry).where(
            AgentContextEntry.user_id == user_id, AgentContextEntry.id == entry_id
        )
        if lock:
            query = query.with_for_update().execution_options(populate_existing=True)
        return await self.session.scalar(query)

    async def changes(self, entry_ids):
        return list(
            (
                await self.session.scalars(
                    select(AgentContextChange)
                    .where(AgentContextChange.entry_id.in_(entry_ids))
                    .order_by(AgentContextChange.id.desc())
                    .limit(200)
                )
            ).all()
        )

    async def reports(self, user_id, project_id, kind=None, report_id=None):
        query = select(ProjectReport).where(
            ProjectReport.user_id == user_id, ProjectReport.project_id == project_id
        )
        if kind:
            query = query.where(ProjectReport.kind == kind)
        if report_id:
            query = query.where(ProjectReport.id == report_id)
        return list(
            (
                await self.session.scalars(
                    query.order_by(ProjectReport.id.desc()).limit(20)
                )
            ).all()
        )

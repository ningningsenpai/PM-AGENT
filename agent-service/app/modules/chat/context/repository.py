"""ContextRepository 仅执行数据库操作，不调用其他仓储或外部服务。"""

from datetime import UTC, datetime

from sqlalchemy import or_, select

from .._persistence import ChatRepositoryBase
from .models import AgentContextChange, AgentContextEntry, AgentContextScope


class ContextRepository(ChatRepositoryBase):
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
                    AgentContextEntry.expires_at
                    > datetime.now(UTC).replace(tzinfo=None),
                ),
            )
        return list(
            (
                await self.session.scalars(
                    query.order_by(AgentContextEntry.id).execution_options(
                        populate_existing=True
                    )
                )
            ).all()
        )

    async def entry(self, user_id, entry_id, *, lock=False):
        query = select(AgentContextEntry).where(
            AgentContextEntry.user_id == user_id, AgentContextEntry.id == entry_id
        )
        if lock:
            query = query.with_for_update().execution_options(populate_existing=True)
        return await self.session.scalar(query)

    async def changes(self, entry_ids, *, limit=200):
        return list(
            (
                await self.session.scalars(
                    select(AgentContextChange)
                    .where(AgentContextChange.entry_id.in_(entry_ids))
                    .order_by(AgentContextChange.id.desc())
                    .limit(limit)
                )
            ).all()
        )

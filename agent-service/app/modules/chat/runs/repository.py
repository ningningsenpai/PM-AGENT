"""RunRepository 仅执行数据库操作，不调用其他仓储或外部服务。"""

from sqlalchemy import select

from .._persistence import ChatRepositoryBase
from .models import AgentRun


class RunRepository(ChatRepositoryBase):
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

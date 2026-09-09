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
        """按用户、操作类型和幂等键查找已有运行，供服务层复用结果或处理冲突。"""
        return await self.session.scalar(
            select(AgentRun).where(
                AgentRun.user_id == user_id,
                AgentRun.operation == operation,
                AgentRun.request_key == key,
            )
        )

    async def active_scope(self, scope_key):
        """查询占用互斥作用域的运行，唯一约束负责裁决并发创建。"""
        return await self.session.scalar(
            select(AgentRun).where(AgentRun.active_scope_key == scope_key)
        )

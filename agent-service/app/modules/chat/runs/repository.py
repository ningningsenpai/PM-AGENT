"""RunRepository 仅执行数据库操作，不调用其他仓储或外部服务。"""

from sqlalchemy import select, update

from .._persistence import ChatRepositoryBase
from .models import AgentRun


class RunRepository(ChatRepositoryBase):
    async def run(self, user_id, run_id, *, lock=False):
        statement = select(AgentRun).where(
            AgentRun.user_id == user_id, AgentRun.id == run_id
        )
        if lock:
            statement = statement.with_for_update()
        return await self.session.scalar(statement)

    async def duplicate(self, user_id, operation, key, *, project_id=None, lock=False):
        """按用户、操作类型和幂等键查找已有运行，供服务层复用结果或处理冲突。"""
        statement = select(AgentRun).where(
            AgentRun.user_id == user_id,
            AgentRun.operation == operation,
            AgentRun.request_key == key,
        )
        if project_id is not None:
            statement = statement.where(AgentRun.project_id == project_id)
        if lock:
            statement = statement.with_for_update()
        return await self.session.scalar(statement)

    async def active_scope(self, scope_key, *, lock=False):
        """查询占用互斥作用域的运行，唯一约束负责裁决并发创建。"""
        statement = select(AgentRun).where(AgentRun.active_scope_key == scope_key)
        if lock:
            statement = statement.with_for_update()
        return await self.session.scalar(statement)

    async def renew_lease(self, user_id, run_id, deadline):
        """仅续租仍在运行且仍持有项目作用域的任务。"""
        result = await self.session.execute(
            update(AgentRun)
            .where(
                AgentRun.user_id == user_id,
                AgentRun.id == run_id,
                AgentRun.status == "running",
                AgentRun.active_scope_key.is_not(None),
            )
            .values(lease_until=deadline)
        )
        return result.rowcount == 1

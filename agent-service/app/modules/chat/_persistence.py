"""Chat 仓储的共同基础；仅提供写入与字段刷新，不提交事务。"""

from sqlalchemy import BigInteger, Integer
from sqlalchemy.ext.asyncio import AsyncSession

ID = BigInteger().with_variant(Integer, "sqlite")


class ChatRepositoryBase:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, row):
        self.session.add(row)
        await self.session.flush()
        # MySQL 无 INSERT RETURNING，显式加载数据库生成的时间字段。
        await self.session.refresh(row)
        return row

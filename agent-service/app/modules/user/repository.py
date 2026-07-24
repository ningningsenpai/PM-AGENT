"""用户数据访问。"""
from __future__ import annotations

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.user.models import User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, user_id: int) -> User | None:
        return await self.session.get(User, user_id)

    async def get_by_email(self, email: str) -> User | None:
        return await self._one(select(User).where(User.email == email))

    async def get_by_username(self, username: str) -> User | None:
        return await self._one(select(User).where(User.username == username))

    async def add(self, user: User) -> User:
        self.session.add(user)
        await self.session.flush()
        return user

    async def _one(self, statement: Select) -> User | None:
        return (await self.session.scalars(statement.limit(1))).first()

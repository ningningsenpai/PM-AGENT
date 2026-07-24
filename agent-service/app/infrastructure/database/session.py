"""异步数据库 Engine 与请求 Session。"""
from __future__ import annotations

from functools import lru_cache
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings


@lru_cache
def get_engine() -> AsyncEngine:
    config = get_settings().database
    return create_async_engine(
        config.url,
        echo=config.echo,
        pool_pre_ping=True,
        pool_size=config.pool_size,
        max_overflow=config.max_overflow,
    )


@lru_cache
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        get_engine(),
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


async def get_db_session() -> AsyncIterator[AsyncSession]:
    async with get_session_factory()() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise

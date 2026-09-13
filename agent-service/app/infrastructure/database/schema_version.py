"""应用代码与 Alembic 数据库版本的一致性检查。"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

EXPECTED_DATABASE_REVISION = "20260912_04"


async def verify_database_revision(engine: AsyncEngine) -> None:
    """数据库未升级到当前代码版本时阻止应用进入就绪状态。"""
    try:
        async with engine.connect() as connection:
            revision = await connection.scalar(
                text("SELECT version_num FROM alembic_version")
            )
    except Exception as exception:
        raise RuntimeError(
            "数据库版本检查失败，请先执行 python -m alembic upgrade head"
        ) from exception
    if revision != EXPECTED_DATABASE_REVISION:
        raise RuntimeError(
            "数据库结构版本与当前代码不一致："
            f"当前={revision or '未知'}，要求={EXPECTED_DATABASE_REVISION}；"
            "请先执行 python -m alembic upgrade head"
        )

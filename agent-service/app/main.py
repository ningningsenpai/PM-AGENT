"""PM-Agent Python 单体后端启动入口。"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from app.api.v1.router import router as api_v1_router
from app.core.config import get_settings
from app.core.errors import install_exception_handlers
from app.core.identifiers import get_snowflake_id_generator
from app.core.logger import get_logger
from app.core.security import get_jwt_manager, get_password_manager
from app.core.trace import TraceMiddleware
from app.infrastructure.database import get_engine
from app.infrastructure.redis import get_redis_provider
from app.infrastructure.storage import get_object_storage
from app.input_context.dependencies import get_normalization_service


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """初始化并释放在线后端依赖。"""
    logger = get_logger(__name__)
    get_settings()
    get_jwt_manager()
    get_password_manager()
    get_snowflake_id_generator()
    get_normalization_service()

    engine = get_engine()
    redis_provider = get_redis_provider()
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        await redis_provider.client.ping()
        get_object_storage()
        logger.info("应用启动初始化完成")
        yield
    finally:
        try:
            await redis_provider.client.aclose()
        finally:
            await engine.dispose()
        logger.info("应用资源释放完成")


app = FastAPI(
    title="PM-Agent Python Backend",
    description="PM-Agent 模块化单体后端",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(TraceMiddleware)
install_exception_handlers(app)
app.include_router(api_v1_router)


@app.get("/internal/health")
def health():
    """健康检查。"""
    return {"status": "UP", "service": "pm-agent-python-backend"}

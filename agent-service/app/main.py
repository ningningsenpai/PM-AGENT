"""PM-Agent Python Agent Service 启动入口。"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.agent import router as agent_router
from app.project.context.detail_analysis.consumer import start_file_detail_consumer
from app.project.context.detail_analysis.settings import get_file_detail_analysis_settings


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_file_detail_analysis_settings()
    runtime = await start_file_detail_consumer(settings) if settings.enabled else None
    try:
        yield
    finally:
        if runtime is not None:
            await runtime.close()

app = FastAPI(
    title="PM-Agent Python Agent Service",
    description="PM-Agent 第 3 阶段 Agent 对话最小闭环 Demo",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(agent_router)


@app.get("/internal/health")
def health():
    """健康检查。"""
    return {"status": "UP", "service": "agent-service"}

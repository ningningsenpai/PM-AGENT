"""PM-Agent Python Agent Service 启动入口。"""
from __future__ import annotations

from fastapi import FastAPI

from app.api.v1.agent import router as agent_router
from app.api.v1.minio_files import router as minio_files_router
from app.api.v1.project_files import router as project_files_router

app = FastAPI(
    title="PM-Agent Python Agent Service",
    description="PM-Agent 第 3 阶段 Agent 对话最小闭环 Demo",
    version="0.1.0",
)

app.include_router(agent_router)
app.include_router(minio_files_router)
app.include_router(project_files_router)


@app.get("/internal/health")
def health():
    """健康检查。"""
    return {"status": "UP", "service": "agent-service"}

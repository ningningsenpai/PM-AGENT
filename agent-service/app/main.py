"""PM-Agent Python 单体后端启动入口。"""
from __future__ import annotations

from fastapi import FastAPI

from app.api.v1.router import router as api_v1_router
from app.core.errors import install_exception_handlers
from app.core.trace import TraceMiddleware

app = FastAPI(
    title="PM-Agent Python Backend",
    description="PM-Agent 模块化单体后端",
    version="1.0.0",
)

app.add_middleware(TraceMiddleware)
install_exception_handlers(app)
app.include_router(api_v1_router)


@app.get("/internal/health")
def health():
    """健康检查。"""
    return {"status": "UP", "service": "pm-agent-python-backend"}

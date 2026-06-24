"""项目上下文 API。"""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/context", tags=["Project Context"])


@router.post("/initProject")
async def initProject():
    """初始化项目上下文请求。"""
    raise NotImplementedError("项目上下文初始化接口暂未接入对外路由")

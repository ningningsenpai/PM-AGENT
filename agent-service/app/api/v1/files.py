"""旧文件接口兼容入口。"""
from __future__ import annotations

from app.api.v1.project_files import legacy_router as router

__all__ = ["router"]

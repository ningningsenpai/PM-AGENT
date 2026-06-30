"""项目上下文模型服务。"""
from __future__ import annotations

import httpx
from pydantic import json

from app.project.context.model.processor import ProjectContextModelProcessor
from app.project.context.model.schemas import ProjectContextModelResponse

__all__ = ["ProjectContextModelService"]


class ProjectContextModelService:
    """项目上下文模型最小调用服务。"""

    def __init__(self) -> None:
        self.client = ProjectContextModelProcessor()


    def generate_user_habits(
            self,
            *,
            existing_habits: str | None = None,
            user_content: str | None = None,
            project_content: str | None = None,
    ) -> str:
        """生成用户习惯。"""
    #     TODO : 后续探讨合适的返回数据格式
        effective_prompt = user_content or project_content
        return self.client.user_habits(existing_habits, effective_prompt)


    @staticmethod
    def health(base_url: str = "http://10.144.48.123:11434", timeout_seconds: float = 3.0) -> dict:
        base_url = base_url.rstrip("/")
        try:
            with httpx.Client(timeout=timeout_seconds) as client:
                response = client.get(f"{base_url}/api/tags")
                response.raise_for_status()
                data = response.json()
            return {
                "healthy": True,
                "base_url": base_url,
                "models": [item.get("name") for item in data.get("models", [])],
                "message": "Ollama 服务正常",
            }
        except Exception as exc:
            return {
                "healthy": False,
                "base_url": base_url,
                "message": f"Ollama 服务不可用：{exc}",
            }

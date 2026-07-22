"""项目上下文模型客户端。"""
from __future__ import annotations

from typing import Any

import httpx

from app.project.context.model.config import load_model_config
from app.project.context.model.schemas import ProjectContextModelConfig, ProjectContextModelResponse

__all__ = ["ProjectContextModelClient"]


class ProjectContextModelClient:
    """项目上下文模型客户端，当前最小实现仅支持 Ollama generate 接口。"""

    def __init__(self, config: ProjectContextModelConfig | None = None) -> None:
        self.config = config or load_model_config()
        if self.config.provider != "ollama":
            raise RuntimeError(f"当前仅支持 ollama provider，实际为：{self.config.provider}")

    def generate(
        self,
        prompt: str,
        *,
        response_format: str | dict[str, Any] | None = None,
    ) -> ProjectContextModelResponse:
        """调用本地项目上下文模型生成内容。"""
        payload: dict[str, Any] = {
            "model": self.config.model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_ctx": self.config.context_size,
            },
        }
        if response_format is not None:
            payload["format"] = response_format
        with httpx.Client(timeout=self.config.timeout_seconds) as client:
            response = client.post(f"{self.config.base_url}/api/generate", json=payload)
            response.raise_for_status()
            data = response.json()
        return self._to_response(data)

    def _to_response(self, data: dict[str, Any]) -> ProjectContextModelResponse:
        return ProjectContextModelResponse(
            provider=self.config.provider,
            model=str(data.get("model") or self.config.model_name),
            content=str(data.get("response") or ""),
            done=bool(data.get("done")),
            finish_reason=str(data.get("done_reason") or ""),
            latency_ms=self._ns_to_ms(data.get("total_duration")),
            prompt_tokens=int(data.get("prompt_eval_count") or 0),
            completion_tokens=int(data.get("eval_count") or 0),
        )

    def _ns_to_ms(self, value: Any) -> int:
        try:
            return int(int(value) / 1_000_000)
        except (TypeError, ValueError):
            return 0

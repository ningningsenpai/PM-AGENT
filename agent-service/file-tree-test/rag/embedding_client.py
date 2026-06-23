"""豆包 Embedding API 客户端。"""

from __future__ import annotations

from typing import Any

import httpx

from config import (
    DOUBAO_API_KEY,
    DOUBAO_EMBEDDING_DIMENSIONS,
    DOUBAO_EMBEDDING_INSTRUCTIONS,
    DOUBAO_EMBEDDING_MODEL,
    DOUBAO_EMBEDDING_URL,
    DOUBAO_SPARSE_EMBEDDING_ENABLED,
)


class EmbeddingConfigError(RuntimeError):
    pass


def _extract_embedding(response_json: dict[str, Any]) -> list[float]:
    data = response_json.get("data")
    if isinstance(data, list) and data:
        first_item = data[0]
        if isinstance(first_item, dict) and "embedding" in first_item:
            return first_item["embedding"]
    if isinstance(data, dict):
        if "embedding" in data:
            return data["embedding"]
        if "dense_embedding" in data:
            return data["dense_embedding"]
    if "embedding" in response_json:
        return response_json["embedding"]
    if "embeddings" in response_json and response_json["embeddings"]:
        return response_json["embeddings"][0]
    raise RuntimeError(f"无法从豆包 Embedding 响应中解析向量，响应字段为：{list(response_json.keys())}，完整响应：{response_json}")


def embed_text(text: str) -> list[float]:
    if not DOUBAO_EMBEDDING_URL:
        raise EmbeddingConfigError("缺少环境变量 DOUBAO_EMBEDDING_URL")
    if not DOUBAO_API_KEY:
        raise EmbeddingConfigError("缺少环境变量 DOUBAO_API_KEY")
    if not DOUBAO_EMBEDDING_MODEL:
        raise EmbeddingConfigError("缺少环境变量 DOUBAO_EMBEDDING_MODEL")

    payload = {
        "model": DOUBAO_EMBEDDING_MODEL,
        "instructions": DOUBAO_EMBEDDING_INSTRUCTIONS,
        "encoding_format": "float",
        "input": [
            {
                "type": "text",
                "text": text,
            }
        ],
        "dimensions": DOUBAO_EMBEDDING_DIMENSIONS,
    }
    if DOUBAO_SPARSE_EMBEDDING_ENABLED:
        payload["sparse_embedding"] = {"type": "enabled"}
    headers = {
        "Authorization": f"Bearer {DOUBAO_API_KEY}",
        "Content-Type": "application/json",
    }
    with httpx.Client(timeout=60) as client:
        response = client.post(DOUBAO_EMBEDDING_URL, headers=headers, json=payload)
        response.raise_for_status()
        return _extract_embedding(response.json())

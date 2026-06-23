"""Qdrant HTTP 客户端封装。"""

from __future__ import annotations

from typing import Any

import httpx

from config import QDRANT_URL


FilterValue = str | int | float | bool


def recreate_collection(collection_name: str, vector_size: int) -> None:
    payload = {
        "vectors": {
            "size": vector_size,
            "distance": "Cosine",
        }
    }
    with httpx.Client(timeout=60) as client:
        client.delete(f"{QDRANT_URL}/collections/{collection_name}")
        response = client.put(f"{QDRANT_URL}/collections/{collection_name}", json=payload)
        response.raise_for_status()


def upsert_points(collection_name: str, points: list[dict[str, Any]]) -> None:
    payload = {"points": points}
    with httpx.Client(timeout=120) as client:
        response = client.put(
            f"{QDRANT_URL}/collections/{collection_name}/points?wait=true",
            json=payload,
        )
        response.raise_for_status()


def search_points(
    collection_name: str,
    query_vector: list[float],
    top_k: int,
    filters: dict[str, FilterValue] | None = None,
) -> list[dict[str, Any]]:
    must_filters = [
        {
            "key": key,
            "match": {"value": value},
        }
        for key, value in (filters or {}).items()
        if value not in (None, "")
    ]
    payload: dict[str, Any] = {
        "vector": query_vector,
        "limit": top_k,
        "with_payload": True,
    }
    if must_filters:
        payload["filter"] = {"must": must_filters}
    with httpx.Client(timeout=60) as client:
        response = client.post(
            f"{QDRANT_URL}/collections/{collection_name}/points/search",
            json=payload,
        )
        response.raise_for_status()
        return response.json()["result"]

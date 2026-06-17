"""一键完成原始对话向量化并写入 Qdrant。"""

from __future__ import annotations

import argparse
import uuid

from config import DEFAULT_VECTOR_SIZE, QDRANT_COLLECTION
from data_loader import load_raw_dialogues
from embedding_client import embed_text
from qdrant_client import recreate_collection, upsert_points


def build_point_id(raw_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, raw_id))


def main() -> None:
    parser = argparse.ArgumentParser(description="将 RAG 原始对话数据向量化并写入 Qdrant")
    parser.add_argument("--collection", default=QDRANT_COLLECTION, help="Qdrant collection 名称")
    parser.add_argument("--batch-size", type=int, default=32, help="批量写入 Qdrant 的数量")
    args = parser.parse_args()

    raw_dialogues = load_raw_dialogues()
    if not raw_dialogues:
        raise RuntimeError("原始数据集为空，无法向量化")

    first_vector = embed_text(raw_dialogues[0].memory_text)
    vector_size = DEFAULT_VECTOR_SIZE or len(first_vector)
    recreate_collection(args.collection, vector_size)

    points = []
    for index, item in enumerate(raw_dialogues, start=1):
        vector = first_vector if index == 1 else embed_text(item.memory_text)
        if len(vector) != vector_size:
            raise RuntimeError(f"向量维度不一致：{item.raw_id} 的维度为 {len(vector)}，期望 {vector_size}")
        points.append(
            {
                "id": build_point_id(item.raw_id),
                "vector": vector,
                "payload": {
                    "raw_id": item.raw_id,
                    "global_index": item.global_index,
                    "project_id": item.project_id,
                    "project_name": item.project_name,
                    "turn_no": item.turn_no,
                    "module": item.module,
                    "status": item.status,
                    "memory_text": item.memory_text,
                },
            }
        )
        if len(points) >= args.batch_size:
            upsert_points(args.collection, points)
            print(f"已写入 {index} / {len(raw_dialogues)} 条向量")
            points = []

    if points:
        upsert_points(args.collection, points)
        print(f"已写入 {len(raw_dialogues)} / {len(raw_dialogues)} 条向量")

    print(f"向量化完成，collection={args.collection}，数据量={len(raw_dialogues)}，向量维度={vector_size}")


if __name__ == "__main__":
    main()

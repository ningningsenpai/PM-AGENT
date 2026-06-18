"""一键完成原始对话向量化并写入 Qdrant。"""

from __future__ import annotations

import argparse
import uuid

from config import DEFAULT_EMBED_FIELDS, DEFAULT_PAYLOAD_FIELDS, DEFAULT_VECTOR_SIZE, QDRANT_COLLECTION
from data_loader import load_raw_dialogues
from embedding_client import embed_text
from qdrant_client import recreate_collection, upsert_points


def build_point_id(raw_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, raw_id))


def parse_fields(fields_text: str | None, default_fields: list[str]) -> list[str]:
    if not fields_text:
        return default_fields
    fields = [field.strip() for field in fields_text.split(",") if field.strip()]
    if not fields:
        raise RuntimeError("字段列表不能为空")
    return fields


def build_embedding_text(item: object, fields: list[str]) -> str:
    parts = []
    for field in fields:
        value = item.get_field_text(field)
        if value:
            parts.append(f"{field}：{value}")
    if not parts:
        raise RuntimeError(f"{item.raw_id} 没有可用于向量化的字段内容")
    return "\n".join(parts)


def build_payload(item: object, fields: list[str], embed_fields: list[str], embedding_text: str) -> dict[str, object]:
    payload = {field: item.get_field_text(field) for field in fields}
    payload["embedding_fields"] = embed_fields
    payload["embedding_text"] = embedding_text
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="将 RAG 原始对话数据向量化并写入 Qdrant")
    parser.add_argument("--collection", default=QDRANT_COLLECTION, help="Qdrant collection 名称")
    parser.add_argument("--embed-fields", default=",".join(DEFAULT_EMBED_FIELDS), help="参与向量化的字段，多个字段用英文逗号分隔")
    parser.add_argument("--payload-fields", default=",".join(DEFAULT_PAYLOAD_FIELDS), help="写入 Qdrant payload 的字段，多个字段用英文逗号分隔")
    parser.add_argument("--batch-size", type=int, default=32, help="批量写入 Qdrant 的数量")
    args = parser.parse_args()

    embed_fields = parse_fields(args.embed_fields, DEFAULT_EMBED_FIELDS)
    payload_fields = parse_fields(args.payload_fields, DEFAULT_PAYLOAD_FIELDS)
    raw_dialogues = load_raw_dialogues()
    if not raw_dialogues:
        raise RuntimeError("原始数据集为空，无法向量化")

    first_embedding_text = build_embedding_text(raw_dialogues[0], embed_fields)
    first_vector = embed_text(first_embedding_text)
    vector_size = DEFAULT_VECTOR_SIZE or len(first_vector)
    recreate_collection(args.collection, vector_size)

    points = []
    for index, item in enumerate(raw_dialogues, start=1):
        embedding_text = first_embedding_text if index == 1 else build_embedding_text(item, embed_fields)
        vector = first_vector if index == 1 else embed_text(embedding_text)
        if len(vector) != vector_size:
            raise RuntimeError(f"向量维度不一致：{item.raw_id} 的维度为 {len(vector)}，期望 {vector_size}")
        points.append(
            {
                "id": build_point_id(item.raw_id),
                "vector": vector,
                "payload": build_payload(item, payload_fields, embed_fields, embedding_text),
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

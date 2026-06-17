"""按指定范围检索问题并输出检索结果。"""

from __future__ import annotations

import argparse

from config import DEFAULT_TOP_K, QDRANT_COLLECTION
from data_loader import load_gold_answers, load_questions, load_raw_dialogues
from embedding_client import embed_text
from qdrant_client import search_points

START_INDEX = 46
END_INDEX = 55


def _lookup_raw_text(raw_map: dict[str, str], raw_id: str) -> str:
    return raw_map.get(raw_id, "")


def _print_raw_items(title: str, raw_ids: list[str], raw_texts: list[str]) -> None:
    print(title)
    if not raw_ids:
        print("无")
        return
    for raw_id, raw_text in zip(raw_ids, raw_texts):
        print(raw_id)
        print(raw_text)


def main() -> None:
    parser = argparse.ArgumentParser(description="执行 RAG 检索测试")
    parser.add_argument("--collection", default=QDRANT_COLLECTION, help="Qdrant collection 名称")
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K, help="检索条数")
    args = parser.parse_args()

    if START_INDEX < 1 or END_INDEX < START_INDEX:
        raise RuntimeError("问题范围参数不合法")

    questions = load_questions()
    raw_dialogues = load_raw_dialogues()
    gold_answers = load_gold_answers()
    raw_map = {item.raw_id: item.memory_text for item in raw_dialogues}

    selected_questions = [item for item in questions if START_INDEX <= item.global_index <= END_INDEX]
    if not selected_questions:
        raise RuntimeError("指定范围内没有问题数据")

    for question in selected_questions:
        gold = gold_answers[question.question_id]
        query_vector = embed_text(question.question_text)
        results = search_points(args.collection, query_vector, question.project_id, args.top_k)
        retrieved_raw_ids = [result["payload"]["raw_id"] for result in results]
        retrieved_texts = [_lookup_raw_text(raw_map, raw_id) for raw_id in retrieved_raw_ids]
        expected_raw_texts = [_lookup_raw_text(raw_map, raw_id) for raw_id in gold.expected_raw_ids]
        hit_count = len(set(retrieved_raw_ids) & set(gold.expected_raw_ids))
        ratio = 0.0 if not retrieved_raw_ids else round(hit_count / len(retrieved_raw_ids), 4)

        print("=" * 120)
        print(f"问题编号: {question.question_id}")
        print(f"输入的问题: {question.question_text}")
        _print_raw_items("检索结果:", retrieved_raw_ids, retrieved_texts)
        _print_raw_items("正确答案:", gold.expected_raw_ids, expected_raw_texts)
        print(f"和预计答案对比的相似度: {ratio}")

    print("=" * 120)
    print(f"检索完成，问题范围: {START_INDEX}-{END_INDEX}，top_k={args.top_k}")


if __name__ == "__main__":
    main()

"""合并 001-003 历史对话 CSV，并统一 raw_id 与 project_id。"""

from __future__ import annotations

import csv
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
INPUT_FILES = [
    BASE_DIR / "001-history_raw_dialogues.csv",
    BASE_DIR / "002-history_raw_dialogues.csv",
    BASE_DIR / "003-history_raw_dialogues.csv",
]
OUTPUT_FILE = BASE_DIR / "007-merged_001_003_history_raw_dialogues.csv"

SNOWFLAKE_EPOCH_MS = 1704067200000
WORKER_ID = 1


def build_snowflake_id(sequence: int) -> str:
    timestamp_part = (SNOWFLAKE_EPOCH_MS + sequence) << 22
    worker_part = WORKER_ID << 12
    return str(timestamp_part | worker_part | sequence)


def project_key(row: dict[str, str]) -> tuple[str, str]:
    project_id = (row.get("project_id") or "NULL").strip() or "NULL"
    project_name = (row.get("project_name") or "NULL").strip() or "NULL"
    return project_id, project_name


def main() -> None:
    merged_rows: list[dict[str, str]] = []
    headers: list[str] | None = None
    project_id_mapping: dict[tuple[str, str], str] = {}

    for input_file in INPUT_FILES:
        with input_file.open("r", encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file)
            if headers is None:
                headers = list(reader.fieldnames or [])
            elif headers != list(reader.fieldnames or []):
                raise RuntimeError(f"CSV 表头不一致：{input_file}")
            for row in reader:
                key = project_key(row)
                if key not in project_id_mapping:
                    project_id_mapping[key] = build_snowflake_id(len(project_id_mapping) + 1)
                row["project_id"] = project_id_mapping[key]
                merged_rows.append(row)

    if headers is None:
        raise RuntimeError("没有读取到 CSV 表头")

    for index, row in enumerate(merged_rows, start=1):
        row["raw_id"] = f"RAW-HISTORY-{index:03d}"
        row["global_index"] = str(index)
        row["turn_no"] = str(index)

    with OUTPUT_FILE.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=headers)
        writer.writeheader()
        writer.writerows(merged_rows)

    print(f"合并完成：{OUTPUT_FILE}")
    print(f"合并行数：{len(merged_rows)}")
    print("project_id 映射：")
    for (old_project_id, project_name), new_project_id in project_id_mapping.items():
        print(f"{old_project_id} / {project_name} -> {new_project_id}")


if __name__ == "__main__":
    main()

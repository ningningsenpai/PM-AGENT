# 手动运行入口：调用正式扫描服务，并暂时把输出写入 tests 目录。
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from app.project_context.model.client import ProjectContextModelClient
from app.project_context.model.prompts import ProjectContextPrompt, build_smoke_test_prompt
from app.project_context.service import ProjectContextScanService


def test_user_habits_prompt_contains_json_merge_rules() -> None:
    prompt = ProjectContextPrompt.USER_HABITS.value
    user_habits_path = Path(__file__).resolve().parent / "user_habits.json"


    assert "existing_habits_json" in prompt
    assert "new_content" in prompt
    assert "只输出合法 JSON" in prompt
    assert "overwritten" in prompt
    assert "evolved" in prompt
    assert "work | life | thinking | specification | tooling | other" in prompt



def test_project_context_model_request() -> None:
    """测试通过 .env 配置请求本地 Ollama 项目上下文模型。"""
    _load_env_file()
    client = ProjectContextModelClient()
    result = client.generate(build_smoke_test_prompt())

    print("模型响应：")
    print(json.dumps(asdict(result), ensure_ascii=False, indent=2))


def _load_env_file() -> None:
    env_path = Path(__file__).resolve().parents[3] / ".env"
    if not env_path.exists():
        raise RuntimeError(f"未找到 .env 文件：{env_path}")

    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def test_main() -> None:
    parser = argparse.ArgumentParser(description="扫描指定根目录并生成文件树结果")
    parser.add_argument("root_path", help="要扫描的根目录")
    parser.add_argument("output_dir", help="输出目录")
    args = parser.parse_args()

    service = ProjectContextScanService()
    result, json_path = service.scan_to_directory(args.root_path, args.output_dir)

    print(f"扫描完成：{result.root_path}")
    print(f"JSON 结果：{json_path}")


def main() -> None:
    root_path = Path(__file__).resolve().parents[3]
    input_dir = root_path.joinpath("file-tree-test")
    output_dir = Path(__file__).resolve().parent

    # service = ProjectContextScanService()
    # result, json_path = service.scan_to_directory(input_dir, output_dir)
    # print(f"扫描完成：{result.root_path}")
    # print(f"JSON 结果：{json_path}")


    changed, update_path = check_file_update(input_dir, output_dir)

    print(f"文件是否更新：{changed}")
    print(f"更新检测索引：{update_path}")


def check_file_update(root_path: Path, output_dir: Path) -> tuple[bool, Path]:
    """检查文件是否更新；有变化时覆盖指定输出目录下的 Project_Index.json。"""
    service = ProjectContextScanService()
    return service.check_update_and_write(root_path, output_dir)


if __name__ == "__main__":
    test_project_context_model_request()

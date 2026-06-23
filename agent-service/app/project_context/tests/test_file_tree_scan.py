# 手动运行入口：调用正式扫描服务，并暂时把输出写入 tests 目录。
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from app.project_context.service import ProjectContextScanService


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
    main()

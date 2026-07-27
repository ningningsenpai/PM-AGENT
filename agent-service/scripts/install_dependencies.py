"""将项目依赖安装到执行脚本所使用的当前 Python 环境。"""
from __future__ import annotations

import importlib
from pathlib import Path
import subprocess
import sys


MINIMUM_PYTHON_VERSION = (3, 11)
REQUIRED_IMPORTS = (
    "ahocorasick",
    "aiosqlite",
    "alembic",
    "asyncmy",
    "fastapi",
    "httpx",
    "jwt",
    "minio",
    "multipart",
    "pwdlib",
    "pydantic",
    "pytest",
    "redis",
    "ruff",
    "sqlalchemy",
    "uvicorn",
)


def configure_console_encoding() -> None:
    """统一 Windows 与其他终端中的中文输出编码。"""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


def run_command(command: list[str], description: str) -> bool:
    """执行安装或校验命令，并输出明确的中文结果。"""
    print(f"\n{description}：{' '.join(command)}")
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as exception:
        print(f"{description}失败，退出码：{exception.returncode}")
        return False
    return True


def verify_imports() -> bool:
    """验证运行、迁移和开发阶段所需模块均可导入。"""
    missing_modules: list[str] = []
    for module_name in REQUIRED_IMPORTS:
        try:
            importlib.import_module(module_name)
        except ImportError:
            missing_modules.append(module_name)

    if missing_modules:
        print(f"以下模块仍无法导入：{', '.join(missing_modules)}")
        return False

    print("依赖导入验证通过。")
    return True


def main() -> int:
    configure_console_encoding()

    if sys.version_info < MINIMUM_PYTHON_VERSION:
        current_version = ".".join(str(item) for item in sys.version_info[:3])
        print(f"当前 Python 版本为 {current_version}，项目要求 Python 3.11 或更高版本。")
        return 1

    service_root = Path(__file__).resolve().parents[1]
    install_target = f"{service_root}[dev]"
    print(f"当前 Python：{sys.executable}")
    print(f"项目目录：{service_root}")

    if not run_command(
        [sys.executable, "-m", "pip", "install", "-e", install_target],
        "安装项目运行与开发依赖",
    ):
        return 1

    if not run_command(
        [sys.executable, "-m", "pip", "check"],
        "检查依赖版本兼容性",
    ):
        return 1

    if not verify_imports():
        return 1

    print("\n所有 Python 依赖已安装到当前环境。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

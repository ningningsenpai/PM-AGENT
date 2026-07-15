import os
from pathlib import Path

__all__ = ["LoadConfig"]

class LoadConfig:
    """加载环境变量配置。"""
    def __init__(self) -> None:
        load_env_file()


def load_env_file() -> None:
    """加载本地 .env 文件；不覆盖已经存在的系统环境变量。"""
    env_file = Path(__file__).resolve().parents[3] / ".env"
    print(f"尝试加载环境变量文件: {env_file}")
    if not env_file.exists():
        print(f"环境变量文件 {env_file} 不存在，请检查文件路径是否正确！")
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        # 不覆盖已经存在的系统环境变量
        os.environ.setdefault(key.strip(), value.strip())
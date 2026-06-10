from functools import lru_cache
from pathlib import Path
import os


class Settings:
    """Agent 服务运行配置。"""

    def __init__(self) -> None:
        self.deepseek_api_key = os.getenv("DEEPSEEK_API_KEY", "")
        self.deepseek_model = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-pro")
        self.deepseek_base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        self.java_backend_base_url = os.getenv("JAVA_BACKEND_BASE_URL", "http://localhost:8080")
        self.demo_mode = not bool(self.deepseek_api_key)


def load_env_file() -> None:
    """加载本地 .env 文件；不覆盖已经存在的系统环境变量。"""
    env_file = Path(__file__).resolve().parents[2] / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


@lru_cache
def get_settings() -> Settings:
    load_env_file()
    return Settings()

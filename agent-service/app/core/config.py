from functools import lru_cache
from pathlib import Path
import os


class Settings:
    """Agent 服务运行配置。"""

    def __init__(self) -> None:
        self.deepseek_api_key = os.getenv("DEEPSEEK_API_KEY", "")
        self.deepseek_model = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-pro")
        self.deepseek_base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        if not self.deepseek_api_key:
            raise RuntimeError(
                "未配置 DEEPSEEK_API_KEY，请在 .env 文件中设置有效的 API Key 后重启服务。"
            )


def load_env_file() -> None:
    """加载本地 .env 文件；不覆盖已经存在的系统环境变量。"""
    env_file = Path(__file__).resolve().parents[2] / ".env"
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

# 缓存配置实例，避免重复加载
@lru_cache
def get_settings() -> Settings:
    load_env_file()
    return Settings()

"""Agent 服务运行配置。

配置层做两件事：
1. 提供按 provider 分组的 LLM 配置（API Key / Base URL / 模型名等）；
2. 提供默认 provider 与请求级 provider 的解析入口。

为了支持本地只跑一家模型时不必填全部 Key，所有 provider 的 API Key 都
采用懒校验策略：启动期不报错，只有被实际选中的 provider 才在第一次
调用时校验。
"""

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
import os



@dataclass
class LLMProviderConfig:
    """单个 LLM 提供方的运行配置。

    - ``api_key``：鉴权用 API Key；
    - ``base_url``：API 根地址；
    - ``model``：默认模型名 / endpoint ID；
    - ``context_window_tokens``：模型最大上下文窗口，用于上下文健康判断；
    - ``reserved_output_tokens``：预留给模型输出的 token 数；
    - ``extra``：厂商特有字段。
    """

    api_key: str = ""
    base_url: str = ""
    model: str = ""
    context_window_tokens: int | None = None
    reserved_output_tokens: int = 4096
    extra: dict = field(default_factory=dict)

    def require_api_key(self, provider: str) -> None:
        """懒校验：调用期发现 Key 缺失时再报中文错误。"""
        if not self.api_key:
            raise RuntimeError(
                f"未配置 {provider} 的 API Key，请在 .env 文件中设置后重启服务。"
            )


class Settings:
    """Agent 服务运行配置。"""

    def __init__(self) -> None:
        # 默认 provider：未在请求中显式指定时使用。
        self.default_llm_provider = os.getenv("DEFAULT_LLM_PROVIDER", "deepseek")
        supported_providers = {"deepseek", "doubao"}
        if self.default_llm_provider not in supported_providers:
            raise ValueError(
                f"未支持的默认模型提供方：{self.default_llm_provider!r}，当前可选：{sorted(supported_providers)}"
            )

        # 按 provider 分组配置；新增厂商时在这里新增一项即可。
        # 注意：环境变量名仅占位，正式接入时若官方文档要求其它命名再调整。
        self.llm: dict[str, LLMProviderConfig] = {
            "deepseek": LLMProviderConfig(
                api_key=os.getenv("DEEPSEEK_API_KEY", ""),
                base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
                model=os.getenv("DEEPSEEK_MODEL", "deepseek-v4-pro"),
                context_window_tokens=int(os.getenv("DEEPSEEK_CONTEXT_WINDOW_TOKENS", 126000)),
                reserved_output_tokens=int(os.getenv("DEEPSEEK_RESERVED_OUTPUT_TOKENS", 4096)),
            ),
            # 豆包（火山方舟）：OpenAI 兼容协议，model 实际为 endpoint id。
            "doubao": LLMProviderConfig(
                api_key=os.getenv("ARK_API_KEY", ""),
                base_url=os.getenv(
                    "ARK_BASE_URL",
                    "https://ark.cn-beijing.volces.com/api/v3",
                ),
                model=os.getenv("DOUBAO_MODEL", ""),  # TODO 接入时填默认 endpoint id
            ),
        }

    def get_llm_config(self, provider: str) -> LLMProviderConfig:
        """按 provider 获取配置；未知 provider 抛中文错误。"""
        if provider not in self.llm:
            raise ValueError(
                f"未配置的模型提供方：{provider!r}，当前已声明：{sorted(self.llm)}"
            )
        return self.llm[provider]


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
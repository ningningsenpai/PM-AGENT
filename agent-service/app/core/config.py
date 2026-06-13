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


def _int_env(name: str, default: int) -> int:
    """读取整数环境变量；非法值按默认值处理。"""
    value = os.getenv(name, "")
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _optional_int_env(name: str) -> int | None:
    """读取可选整数环境变量；缺失、空字符串、0 或非法值均视为未配置。"""
    value = os.getenv(name, "")
    if not value:
        return None
    try:
        parsed = int(value)
    except ValueError:
        return None
    return parsed or None


@dataclass
class LLMProviderConfig:
    """单个 LLM 提供方的运行配置。

    - ``api_key``：鉴权用 API Key；
    - ``base_url``：API 根地址；
    - ``model``：默认模型名 / endpoint ID；
    - ``context_window_tokens``：模型最大上下文窗口，用于上下文健康判断；
    - ``reserved_output_tokens``：预留给模型输出的 token 数；
    - ``extra``：厂商特有字段，例如 MiniMax 的 ``group_id``。
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

        # 按 provider 分组配置；新增厂商时在这里新增一项即可。
        # 注意：环境变量名仅占位，正式接入时若官方文档要求其它命名再调整。
        self.llm: dict[str, LLMProviderConfig] = {
            "deepseek": LLMProviderConfig(
                api_key=os.getenv("DEEPSEEK_API_KEY", ""),
                base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
                model=os.getenv("DEEPSEEK_MODEL", "deepseek-v4-pro"),
                context_window_tokens=_optional_int_env("DEEPSEEK_CONTEXT_WINDOW_TOKENS"),
                reserved_output_tokens=_int_env("DEEPSEEK_RESERVED_OUTPUT_TOKENS", 4096),
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
            # 智谱 GLM：OpenAI 兼容协议。
            "glm": LLMProviderConfig(
                api_key=os.getenv("ZHIPU_API_KEY", ""),
                base_url=os.getenv(
                    "GLM_BASE_URL",
                    "https://open.bigmodel.cn/api/paas/v4",
                ),
                model=os.getenv("GLM_MODEL", "glm-4"),  # TODO 确认正式版本号
            ),
            # Moonshot Kimi：OpenAI 兼容协议。
            "kimi": LLMProviderConfig(
                api_key=os.getenv("MOONSHOT_API_KEY", ""),
                base_url=os.getenv("KIMI_BASE_URL", "https://api.moonshot.cn/v1"),
                model=os.getenv("KIMI_MODEL", "moonshot-v1-8k"),  # TODO 确认正式型号
            ),
            # MiniMax：自有协议，请求体字段与流式分隔符与 OpenAI 略有差异。
            "minimax": LLMProviderConfig(
                api_key=os.getenv("MINIMAX_API_KEY", ""),
                base_url=os.getenv("MINIMAX_BASE_URL", "https://api.minimax.chat/v1"),
                model=os.getenv("MINIMAX_MODEL", ""),  # TODO 接入时填默认模型
                extra={"group_id": os.getenv("MINIMAX_GROUP_ID", "")},
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

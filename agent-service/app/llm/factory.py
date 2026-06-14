"""LLM 客户端工厂。

负责把 ``provider`` 名称解析为可用的客户端实例。导入本模块时会自动触发
``app.llm.clients`` 包内所有客户端的注册（依赖各 client 模块的导入副作用）。
"""

from functools import lru_cache

from app.core.config import Settings
from app.llm.base import BaseLLMClient
from app.llm.registry import get_llm_class

# 触发各厂商客户端模块的导入，从而执行 @register_llm 装饰器。
# 注意：这一行必须保留，import 副作用即为注册行为。
from app.llm import clients  # noqa: F401  pylint: disable=unused-import


@lru_cache(maxsize=None)
def _build_client(provider: str, settings_id: int) -> BaseLLMClient:
    """按 (provider, settings 实例 id) 缓存客户端实例。

    用 ``id(settings)`` 作为缓存维度而非 settings 本身，是因为 Settings
    没有实现 ``__hash__``；同时单进程内 Settings 通常是单例，命中率高。
    """
    # 仅用于消除未使用参数告警，真正缓存键由 lru_cache 计算。
    del settings_id
    cls = get_llm_class(provider)
    return cls(_settings_holder[provider])


# 旁路存储：用 provider 名映射回 settings，配合 lru_cache 的 id 维度使用。
_settings_holder: dict[str, Settings] = {}


def get_llm_client(provider: str, settings: Settings) -> BaseLLMClient:
    """获取指定 provider 的客户端实例；同 provider + 同 settings 复用。"""
    _settings_holder[provider] = settings
    return _build_client(provider, id(settings))

"""LLM 客户端注册表。

通过 ``@register_llm("provider_name")`` 装饰器将具体客户端类登记到全局
注册表中，工厂据此按名称查找实现类，避免每新增一家模型就要修改
``if/elif`` 分支。
"""

from app.llm.base import BaseLLMClient

# provider 名称 → 客户端类
_REGISTRY: dict[str, type[BaseLLMClient]] = {}


def register_llm(name: str):
    """装饰器：把客户端类按 provider 名注册到全局表。"""

    def decorator(cls: type[BaseLLMClient]) -> type[BaseLLMClient]:
        if not issubclass(cls, BaseLLMClient):
            raise TypeError(f"{cls.__name__} 必须继承 BaseLLMClient 才能注册为 LLM 客户端")
        if name in _REGISTRY:
            raise RuntimeError(f"LLM provider {name!r} 已经被注册，存在重复登记")
        # 强制类属性 provider 与装饰器名一致，避免后续配置查找出错。
        cls.provider = name
        _REGISTRY[name] = cls
        return cls

    return decorator


def get_llm_class(name: str) -> type[BaseLLMClient]:
    """按名称查找客户端类；未注册则抛出业务异常。"""
    if name not in _REGISTRY:
        raise ValueError(
            f"未注册的模型提供方：{name!r}，当前可选：{sorted(_REGISTRY)}"
        )
    return _REGISTRY[name]


def list_providers() -> list[str]:
    """返回已注册的所有 provider 名称，便于 /healthz 或调试输出。"""
    return sorted(_REGISTRY)

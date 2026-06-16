"""LLM 客户端实现集合。

导入本包会触发 DeepSeek 与豆包客户端的 ``@register_llm`` 装饰器执行，
从而完成注册。
"""

from app.llm.clients import deepseek_client  # noqa: F401
from app.llm.clients import doubao_client  # noqa: F401

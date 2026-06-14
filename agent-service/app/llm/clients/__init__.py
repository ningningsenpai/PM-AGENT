"""LLM 客户端实现集合。

导入本包会触发各厂商客户端的 ``@register_llm`` 装饰器执行，从而完成注册。
新增厂商时：在本目录新增模块并在下方追加 import 即可被工厂识别。
"""

from app.llm.clients import deepseek_client  # noqa: F401
from app.llm.clients import doubao_client  # noqa: F401
from app.llm.clients import glm_client  # noqa: F401
from app.llm.clients import kimi_client  # noqa: F401
from app.llm.clients import minimax_client  # noqa: F401

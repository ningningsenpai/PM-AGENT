"""豆包模型适配器（火山方舟）。

火山方舟提供 OpenAI 兼容协议，``model`` 字段实际填写的是
方舟控制台创建的 endpoint id（形如 ``ep-2024xxxxxx``）。
正式接入时只需在 ``.env`` 中配置 ``ARK_API_KEY`` 与 ``DOUBAO_MODEL``。

TODO 正式接入前确认 SDK 版本：
- 方案一：直接 HTTP 调用（当前实现）；
- 方案二：使用 ``volcengine-python-sdk`` 官方包。
"""

from app.llm.clients.openai_compatible import OpenAICompatibleClient
from app.llm.registry import register_llm


@register_llm("doubao")
class DoubaoClient(OpenAICompatibleClient):
    """豆包模型适配器；走火山方舟 OpenAI 兼容接口。"""

    supports_real_usage = True

"""智谱 GLM 模型适配器。

智谱 BigModel 平台提供 OpenAI 兼容协议，
默认模型 ``glm-4``（正式版本号以官方文档为准）。

TODO 正式接入前确认：
- 模型默认值（glm-4 / glm-4-plus / glm-4-flash 等）；
- 是否需要使用官方 ``zhipuai`` SDK 替换 HTTP 调用；
- 鉴权是否需要特殊 JWT 包装（部分老接口要求）。
"""

from app.llm.clients.openai_compatible import OpenAICompatibleClient
from app.llm.registry import register_llm


@register_llm("glm")
class GLMClient(OpenAICompatibleClient):
    """智谱 GLM 模型适配器。"""

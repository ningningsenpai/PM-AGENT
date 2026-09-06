"""DeepSeek 模型适配器。

复用 OpenAI 兼容协议，并补充已知模型的输出上限。
"""

from app.llm.clients.openai_compatible import OpenAICompatibleClient
from app.llm.contracts import LLMCapabilities
from app.llm.registry import register_llm


@register_llm("deepseek")
class DeepSeekClient(OpenAICompatibleClient):
    """DeepSeek 模型适配器；默认模型由 ``DEEPSEEK_MODEL`` 配置。"""

    supports_real_usage = True
    capabilities = LLMCapabilities(
        native_tool_calling=True,
        streaming_tool_calling=True,
        reasoning_content_round_trip=True,
    )

    def _build_body(self, messages: list[dict], stream: bool, **kwargs) -> dict:
        body = super()._build_body(messages, stream, **kwargs)
        if (
            not stream
            and body.get("response_format") == {"type": "json_object"}
            and not body.get("tools")
        ):
            # 结构化抽取需要完整 JSON，避免默认思考过程耗尽生成额度。
            body["thinking"] = {"type": "disabled"}
        return body

    @property
    def max_output_tokens(self) -> int | None:
        # V4 官方最大输出为 384K，与模型的上下文窗口分别限制。
        if self.config.model in {
            "deepseek-v4-pro",
            "deepseek-v4-flash",
            "deepseek-v4-flash-vision-exp",
        }:
            return 384000
        return None

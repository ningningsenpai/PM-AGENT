from typing import Literal

from pydantic import BaseModel, Field, model_validator


class LLMTokenUsage(BaseModel):
    """单轮 LLM 调用的 token 用量统计。"""

    provider: str = Field(..., description="模型提供方，例如 deepseek")
    model: str | None = Field(default=None, description="实际调用的模型名称")
    round_index: int | None = Field(default=None, description="当前会话中的 user 轮次")
    input_tokens: int | None = Field(default=None, description="输入 token 数，对应 prompt_tokens")
    output_tokens: int | None = Field(default=None, description="输出 token 数，对应 completion_tokens")
    total_tokens: int | None = Field(default=None, description="总 token 数")
    source: Literal["provider_usage"] = Field(
        default="provider_usage",
        description="token 统计来源；当前仅支持 provider 原始 usage",
    )

    @model_validator(mode="after")
    def _fill_total_tokens(self) -> "LLMTokenUsage":
        """当总 token 缺失时，由输入 + 输出自动补齐。"""
        if (
            self.total_tokens is None
            and self.input_tokens is not None
            and self.output_tokens is not None
        ):
            self.total_tokens = self.input_tokens + self.output_tokens
        return self

    @classmethod
    def from_openai_compatible_usage(
        cls,
        *,
        provider: str,
        model: str | None,
        usage: dict | None,
    ) -> "LLMTokenUsage | None":
        """从 OpenAI 兼容协议的 usage 对象构建统一 token 统计。"""
        if not usage:
            return None
        return cls(
            provider=provider,
            model=model,
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
            total_tokens=usage.get("total_tokens"),
        )


class LLMChatResult(BaseModel):
    """非流式 LLM 调用结果。"""

    content: str = Field(default="", description="模型返回的完整文本")
    usage: LLMTokenUsage | None = Field(default=None, description="本轮 token 用量")


class LLMStreamChunk(BaseModel):
    """流式 LLM 调用的单个输出片段。"""

    content: str = Field(default="", description="本次流式片段的文本内容")
    usage: LLMTokenUsage | None = Field(
        default=None,
        description="流结束时返回的 token 用量；普通 token 片段为空",
    )

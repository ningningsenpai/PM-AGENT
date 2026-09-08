"""结构化生成器的统一装配，具体输出预算由业务模块传入。"""

from app.core.config import get_settings
from app.llm.factory import get_llm_client
from app.llm.structured import StructuredJsonGenerator


def get_structured_generator(max_tokens):
    settings = get_settings().llm
    return StructuredJsonGenerator(
        get_llm_client(settings.default_llm_provider, settings),
        max_tokens=max_tokens,
        timeout_seconds=180,
    )

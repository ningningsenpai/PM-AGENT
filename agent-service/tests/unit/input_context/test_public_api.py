"""输入上下文公共边界和归一化兼容性测试。"""

from app.input_context import (
    NormalizationService,
    create_default_normalization_service,
)
from app.normalization import (
    NormalizationService as LegacyNormalizationService,
)


def test_input_context_reuses_compatible_normalization_api() -> None:
    assert NormalizationService is LegacyNormalizationService
    assert isinstance(create_default_normalization_service(), NormalizationService)

"""输入上下文应用级只读依赖。"""

from __future__ import annotations

from functools import lru_cache
from app.input_context.normalization import (
    NormalizationService,
    create_default_normalization_service,
)


@lru_cache
def get_normalization_service() -> NormalizationService:
    """构建并预热唯一归一化服务，复用词库和自动机缓存。"""
    service = create_default_normalization_service()
    service.validate_runtime()
    return service

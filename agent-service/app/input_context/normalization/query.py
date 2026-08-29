"""用户查询归一化的运行时降级边界。"""

from __future__ import annotations

from dataclasses import dataclass

from app.input_context.normalization.preprocessing import TextNormalizer
from app.input_context.normalization.schemas import NormalizationResult
from app.input_context.normalization.service import NormalizationService


@dataclass(frozen=True, slots=True)
class QueryNormalization:
    """保留成功结果或明确降级状态的查询归一化结果。"""

    raw_text: str
    cleaned_text: str
    result: NormalizationResult | None
    warnings: tuple[str, ...] = ()
    degraded: bool = False

    @property
    def normalized_terms(self) -> tuple[str, ...]:
        return self.result.normalized_terms if self.result is not None else ()


class QueryNormalizer:
    """统一执行在线查询归一化，失败时只退回基础文本处理。"""

    def __init__(self, service: NormalizationService) -> None:
        self._service = service
        self._text_normalizer = TextNormalizer()

    def normalize(self, raw_text: str, *, project_id: int) -> QueryNormalization:
        try:
            result = self._service.normalize_query(
                raw_text,
                project_id=str(project_id),
            )
        except (OSError, RuntimeError, ValueError):
            return QueryNormalization(
                raw_text=raw_text,
                cleaned_text=self._text_normalizer.normalize_for_matching(raw_text),
                result=None,
                warnings=("项目词库不可用，已退化为基础文本归一化",),
                degraded=True,
            )
        return QueryNormalization(
            raw_text=raw_text,
            cleaned_text=result.cleaned_text,
            result=result,
            warnings=tuple(getattr(result, "warnings", ())),
            degraded=bool(getattr(result, "warnings", ())),
        )

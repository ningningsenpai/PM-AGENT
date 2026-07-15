"""内容归一化对外服务入口。"""
from __future__ import annotations

from pathlib import Path

from app.normalization.lexicon.json_provider import DEFAULT_LEXICON_ROOT, JsonLexiconProvider
from app.normalization.lexicon.merger import LexiconMerger
from app.normalization.lexicon.registry import LexiconRegistry
from app.normalization.lexicon.validator import LexiconValidator
from app.normalization.mapping import SynonymMapper
from app.normalization.matching import AhoMatcher, LongestMatchResolver
from app.normalization.pipeline import NormalizationPipeline
from app.normalization.preprocessing import TextNormalizer
from app.normalization.schemas import NormalizationResult

__all__ = ["NormalizationService", "create_default_normalization_service"]


class NormalizationService:
    """为查询、项目内容和结构化字段提供统一归一化入口。"""

    def __init__(
        self,
        registry: LexiconRegistry,
        pipeline: NormalizationPipeline,
    ) -> None:
        self.registry = registry
        self.pipeline = pipeline

    def normalize_query(
        self,
        text: str,
        *,
        tenant_id: int = 0,
        project_id: str | None = None,
        domain: str = "project_management",
    ) -> NormalizationResult:
        """归一化用户查询，不覆盖原始输入。"""
        return self._normalize(text, tenant_id=tenant_id, project_id=project_id, domain=domain)

    def normalize_document(
        self,
        text: str,
        *,
        tenant_id: int = 0,
        project_id: str | None = None,
        domain: str = "project_management",
    ) -> NormalizationResult:
        """归一化待索引项目内容，确保与查询侧使用相同版本。"""
        return self._normalize(text, tenant_id=tenant_id, project_id=project_id, domain=domain)

    def normalize_structured_field(
        self,
        text: str,
        *,
        tenant_id: int = 0,
        project_id: str | None = None,
        domain: str = "project_management",
    ) -> NormalizationResult:
        """归一化通过结构校验后的 LLM 业务字段。"""
        return self._normalize(text, tenant_id=tenant_id, project_id=project_id, domain=domain)

    def reload_lexicons(
        self,
        *,
        tenant_id: int | None = None,
        project_id: str | None = None,
    ) -> None:
        """在部署新词库版本后使对应自动机缓存失效。"""
        self.registry.invalidate(tenant_id=tenant_id, project_id=project_id)

    def _normalize(
        self,
        text: str,
        *,
        tenant_id: int,
        project_id: str | None,
        domain: str,
    ) -> NormalizationResult:
        compiled_lexicon = self.registry.get_or_build(
            tenant_id=tenant_id,
            project_id=project_id,
            domain=domain,
        )
        return self.pipeline.run(text, compiled_lexicon)


def create_default_normalization_service(
    lexicon_root: Path = DEFAULT_LEXICON_ROOT,
) -> NormalizationService:
    """使用本地 JSON 词库组装第一版归一化服务。"""
    text_normalizer = TextNormalizer()
    matcher = AhoMatcher(text_normalizer)
    registry = LexiconRegistry(
        provider=JsonLexiconProvider(lexicon_root),
        validator=LexiconValidator(text_normalizer),
        merger=LexiconMerger(text_normalizer),
        matcher=matcher,
    )
    pipeline = NormalizationPipeline(
        text_normalizer=text_normalizer,
        matcher=matcher,
        resolver=LongestMatchResolver(),
        synonym_mapper=SynonymMapper(),
    )
    return NormalizationService(registry=registry, pipeline=pipeline)

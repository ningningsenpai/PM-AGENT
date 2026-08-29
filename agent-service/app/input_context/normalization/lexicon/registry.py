"""术语库版本与只读自动机缓存注册中心。"""

from __future__ import annotations

from threading import RLock

from app.input_context.normalization.lexicon.merger import LexiconMerger
from app.input_context.normalization.lexicon.provider import LexiconProvider
from app.input_context.normalization.lexicon.validator import LexiconValidator
from app.input_context.normalization.matching import AhoMatcher, CompiledLexicon

__all__ = ["LexiconRegistry"]


class LexiconRegistry:
    """按业务上下文复用已发布词库的只读自动机。"""

    def __init__(
        self,
        provider: LexiconProvider,
        validator: LexiconValidator,
        merger: LexiconMerger,
        matcher: AhoMatcher,
    ) -> None:
        self.provider = provider
        self.validator = validator
        self.merger = merger
        self.matcher = matcher
        self._context_fingerprints: dict[tuple[int, str, str], str] = {}
        self._compiled_cache: dict[tuple[int, str, str], CompiledLexicon] = {}
        self._lock = RLock()

    def get_or_build(
        self,
        *,
        tenant_id: int = 0,
        project_id: str | None = None,
        domain: str = "project_management",
        force_reload: bool = False,
    ) -> CompiledLexicon:
        """获取上下文对应自动机，首次访问或强制刷新时重新构建。"""
        normalized_project_id = str(project_id) if project_id is not None else ""
        context_key = (tenant_id, normalized_project_id, domain)

        with self._lock:
            fingerprint = self._context_fingerprints.get(context_key)
            if fingerprint is not None and not force_reload:
                cached = self._compiled_cache.get(
                    (tenant_id, normalized_project_id, fingerprint)
                )
                if cached is not None:
                    return cached

            common_manifest = self.provider.load_common()
            domain_manifest = self.provider.load_domain(domain)
            project_manifest = (
                self.provider.load_project(normalized_project_id)
                if normalized_project_id
                else None
            )

            manifests = [common_manifest, domain_manifest]
            if project_manifest is not None:
                manifests.append(project_manifest)
            for manifest in manifests:
                report = self.validator.validate_manifest(
                    manifest, require_published=True
                )
                self.validator.ensure_valid(report)

            merged_lexicon = self.merger.merge(
                common_manifest,
                domain_manifest,
                project_manifest,
            )
            self.validator.ensure_valid(self.validator.validate_merged(merged_lexicon))
            compiled_lexicon = self.matcher.compile(merged_lexicon)

            fingerprint = merged_lexicon.version_set.merged_fingerprint
            cache_key = (tenant_id, normalized_project_id, fingerprint)
            self._compiled_cache[cache_key] = compiled_lexicon
            self._context_fingerprints[context_key] = fingerprint
            return compiled_lexicon

    def invalidate(
        self,
        *,
        tenant_id: int | None = None,
        project_id: str | None = None,
    ) -> None:
        """使指定上下文缓存失效；不传条件时清空全部缓存。"""
        with self._lock:
            if tenant_id is None and project_id is None:
                self._context_fingerprints.clear()
                self._compiled_cache.clear()
                return

            normalized_project_id = str(project_id) if project_id is not None else None
            context_keys = [
                key
                for key in self._context_fingerprints
                if (tenant_id is None or key[0] == tenant_id)
                and (normalized_project_id is None or key[1] == normalized_project_id)
            ]
            for context_key in context_keys:
                fingerprint = self._context_fingerprints.pop(context_key)
                self._compiled_cache.pop(
                    (context_key[0], context_key[1], fingerprint), None
                )

    @property
    def cache_size(self) -> int:
        """返回当前已编译自动机数量。"""
        return len(self._compiled_cache)

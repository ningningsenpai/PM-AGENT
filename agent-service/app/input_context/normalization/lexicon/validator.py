"""术语库结构、别名冲突和发布条件校验。"""

from __future__ import annotations

from app.input_context.normalization.lexicon.models import (
    IssueSeverity,
    LexiconIssue,
    LexiconManifest,
    LexiconScope,
    LexiconStatus,
    MergedLexicon,
    ValidationReport,
)
from app.input_context.normalization.preprocessing import TextNormalizer

__all__ = ["LexiconValidationError", "LexiconValidator"]


class LexiconValidationError(RuntimeError):
    """术语库存在阻断构建或发布的问题。"""


class LexiconValidator:
    """在自动机构建前检查单库结构和合并结果。"""

    def __init__(self, text_normalizer: TextNormalizer) -> None:
        self.text_normalizer = text_normalizer

    def validate_manifest(
        self,
        manifest: LexiconManifest,
        *,
        require_published: bool = False,
    ) -> ValidationReport:
        """校验单个术语库的标识、状态、词条和别名唯一性。"""
        issues: list[LexiconIssue] = []
        self._validate_manifest_metadata(manifest, require_published, issues)

        term_ids: set[str] = set()
        canonical_owners: dict[str, str] = {}
        alias_owners: dict[str, str] = {}

        for entry in manifest.entries:
            self._validate_required_entry_fields(
                manifest,
                entry.term_id,
                entry.canonical,
                entry.category,
                entry.source,
                issues,
            )
            if entry.term_id in term_ids:
                issues.append(
                    self._error(
                        "duplicate_term_id", "词条标识重复", manifest, entry.term_id
                    )
                )
            term_ids.add(entry.term_id)

            normalized_canonical = self.text_normalizer.normalize_for_matching(
                entry.canonical
            )
            canonical_owner = canonical_owners.get(normalized_canonical)
            if canonical_owner is not None and canonical_owner != entry.term_id:
                issues.append(
                    self._error(
                        "duplicate_canonical",
                        f"标准术语已由词条 {canonical_owner} 使用",
                        manifest,
                        entry.term_id,
                        entry.canonical,
                    )
                )
            canonical_owners[normalized_canonical] = entry.term_id

            local_aliases: set[str] = set()
            for alias in (entry.canonical, *entry.aliases):
                normalized_alias = self.text_normalizer.normalize_for_matching(alias)
                if not normalized_alias:
                    issues.append(
                        self._error(
                            "empty_alias",
                            "别名清洗后不能为空",
                            manifest,
                            entry.term_id,
                            alias,
                        )
                    )
                    continue
                if len(normalized_alias) == 1:
                    issues.append(
                        self._warning(
                            "short_alias",
                            "单字符别名可能造成大量误召回",
                            manifest,
                            entry.term_id,
                            alias,
                        )
                    )
                if normalized_alias in local_aliases:
                    issues.append(
                        self._warning(
                            "duplicate_alias",
                            "词条内部存在重复别名",
                            manifest,
                            entry.term_id,
                            alias,
                        )
                    )
                    continue
                local_aliases.add(normalized_alias)

                alias_owner = alias_owners.get(normalized_alias)
                if alias_owner is not None and alias_owner != entry.term_id:
                    issues.append(
                        self._error(
                            "ambiguous_alias",
                            f"别名已映射到词条 {alias_owner}",
                            manifest,
                            entry.term_id,
                            alias,
                        )
                    )
                alias_owners[normalized_alias] = entry.term_id

        return ValidationReport(issues=tuple(issues))

    def validate_merged(self, merged_lexicon: MergedLexicon) -> ValidationReport:
        """确认合并结果不存在残留别名冲突。"""
        issues: list[LexiconIssue] = []
        alias_owners: dict[str, str] = {}
        for entry in merged_lexicon.entries:
            for alias in entry.aliases:
                normalized_alias = self.text_normalizer.normalize_for_matching(alias)
                owner = alias_owners.get(normalized_alias)
                if owner is not None and owner != entry.term_id:
                    issues.append(
                        LexiconIssue(
                            severity=IssueSeverity.ERROR,
                            code="merged_alias_conflict",
                            message=f"合并结果中的别名仍同时属于词条 {owner} 和 {entry.term_id}",
                            lexicon_id=entry.lexicon_id,
                            term_id=entry.term_id,
                            alias=alias,
                        )
                    )
                alias_owners[normalized_alias] = entry.term_id
        return ValidationReport(issues=tuple(issues))

    @staticmethod
    def ensure_valid(report: ValidationReport) -> None:
        """在报告含错误时阻断后续构建。"""
        if not report.has_errors:
            return
        messages = "；".join(item.message for item in report.errors[:5])
        raise LexiconValidationError(f"术语库校验失败：{messages}")

    def _validate_manifest_metadata(
        self,
        manifest: LexiconManifest,
        require_published: bool,
        issues: list[LexiconIssue],
    ) -> None:
        if not manifest.lexicon_id.strip():
            issues.append(
                self._error("empty_lexicon_id", "术语库标识不能为空", manifest)
            )
        if not manifest.version.strip():
            issues.append(self._error("empty_version", "术语库版本不能为空", manifest))
        if manifest.scope is LexiconScope.PROJECT and not manifest.scope_id:
            issues.append(
                self._error("missing_scope_id", "项目术语库必须声明 scope_id", manifest)
            )
        if manifest.status is LexiconStatus.DISABLED:
            issues.append(
                self._error("disabled_lexicon", "已禁用术语库不能参与构建", manifest)
            )
        if require_published and manifest.status is not LexiconStatus.PUBLISHED:
            issues.append(
                self._error(
                    "unpublished_lexicon", "运行时只能加载已发布术语库", manifest
                )
            )

    @staticmethod
    def _validate_required_entry_fields(
        manifest: LexiconManifest,
        term_id: str,
        canonical: str,
        category: str,
        source: str,
        issues: list[LexiconIssue],
    ) -> None:
        required_fields = {
            "term_id": term_id,
            "canonical": canonical,
            "category": category,
            "source": source,
        }
        for field_name, value in required_fields.items():
            if not value.strip():
                issues.append(
                    LexiconIssue(
                        severity=IssueSeverity.ERROR,
                        code=f"empty_{field_name}",
                        message=f"词条字段 {field_name} 不能为空",
                        lexicon_id=manifest.lexicon_id,
                        term_id=term_id or None,
                    )
                )

    @staticmethod
    def _error(
        code: str,
        message: str,
        manifest: LexiconManifest,
        term_id: str | None = None,
        alias: str | None = None,
    ) -> LexiconIssue:
        return LexiconIssue(
            severity=IssueSeverity.ERROR,
            code=code,
            message=message,
            lexicon_id=manifest.lexicon_id,
            term_id=term_id,
            alias=alias,
        )

    @staticmethod
    def _warning(
        code: str,
        message: str,
        manifest: LexiconManifest,
        term_id: str | None = None,
        alias: str | None = None,
    ) -> LexiconIssue:
        return LexiconIssue(
            severity=IssueSeverity.WARNING,
            code=code,
            message=message,
            lexicon_id=manifest.lexicon_id,
            term_id=term_id,
            alias=alias,
        )

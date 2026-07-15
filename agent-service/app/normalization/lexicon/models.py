"""术语词条、术语库清单和版本模型。"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "IssueSeverity",
    "LexiconEntry",
    "LexiconIssue",
    "LexiconManifest",
    "LexiconOverrideRecord",
    "LexiconScope",
    "LexiconStatus",
    "LexiconVersionSet",
    "MergedLexicon",
    "ResolvedLexiconEntry",
    "ValidationReport",
]


class LexiconScope(str, Enum):
    """术语库作用域。"""

    COMMON = "common"
    DOMAIN = "domain"
    PROJECT = "project"


class LexiconStatus(str, Enum):
    """术语库发布状态。"""

    DRAFT = "draft"
    PUBLISHED = "published"
    DISABLED = "disabled"


class IssueSeverity(str, Enum):
    """术语库校验问题级别。"""

    ERROR = "error"
    WARNING = "warning"


class LexiconEntry(BaseModel):
    """单个来源文件中的原始术语词条。"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    term_id: str
    canonical: str
    aliases: tuple[str, ...] = Field(default_factory=tuple)
    category: str
    tags: tuple[str, ...] = Field(default_factory=tuple)
    priority: int = 0
    enabled: bool = True
    source: str
    override_term_id: str | None = None


class LexiconManifest(BaseModel):
    """一个可独立发布的术语库清单。"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    lexicon_id: str
    version: str
    scope: LexiconScope
    scope_id: str | None = None
    status: LexiconStatus
    description: str
    entries: tuple[LexiconEntry, ...] = Field(default_factory=tuple)


class ResolvedLexiconEntry(BaseModel):
    """合并后携带来源作用域的运行时词条。"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    term_id: str
    canonical: str
    aliases: tuple[str, ...]
    category: str
    tags: tuple[str, ...]
    priority: int
    source: str
    override_term_id: str | None = None
    lexicon_id: str
    scope: LexiconScope
    scope_id: str | None = None


class LexiconOverrideRecord(BaseModel):
    """高优先级词条显式覆盖低优先级别名的记录。"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    alias: str
    overridden_term_id: str
    overriding_term_id: str
    overriding_scope: LexiconScope


class LexiconVersionSet(BaseModel):
    """一次合并所使用的三级词库版本集合。"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    common_lexicon_id: str
    common_version: str
    domain_lexicon_id: str
    domain_version: str
    project_lexicon_id: str | None = None
    project_version: str | None = None
    merged_fingerprint: str


class MergedLexicon(BaseModel):
    """通过合并和冲突处理后的不可变术语库。"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    entries: tuple[ResolvedLexiconEntry, ...]
    version_set: LexiconVersionSet
    override_records: tuple[LexiconOverrideRecord, ...] = Field(default_factory=tuple)


class LexiconIssue(BaseModel):
    """结构或语义校验产生的单个问题。"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    severity: IssueSeverity
    code: str
    message: str
    lexicon_id: str | None = None
    term_id: str | None = None
    alias: str | None = None


class ValidationReport(BaseModel):
    """术语库校验报告。"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    issues: tuple[LexiconIssue, ...] = Field(default_factory=tuple)

    @property
    def has_errors(self) -> bool:
        """返回报告中是否存在阻断发布的错误。"""
        return any(item.severity is IssueSeverity.ERROR for item in self.issues)

    @property
    def errors(self) -> tuple[LexiconIssue, ...]:
        """返回全部错误。"""
        return tuple(item for item in self.issues if item.severity is IssueSeverity.ERROR)

    @property
    def warnings(self) -> tuple[LexiconIssue, ...]:
        """返回全部警告。"""
        return tuple(item for item in self.issues if item.severity is IssueSeverity.WARNING)

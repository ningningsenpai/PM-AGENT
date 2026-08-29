"""本地 JSON 术语库来源实现。"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.input_context.normalization.lexicon.models import (
    LexiconManifest,
    LexiconScope,
)
from app.input_context.normalization.lexicon.provider import LexiconProvider

__all__ = ["DEFAULT_LEXICON_ROOT", "JsonLexiconProvider", "LexiconLoadError"]


DEFAULT_LEXICON_ROOT = Path(__file__).resolve().parents[4] / "resources" / "lexicons"
_SAFE_FILE_IDENTIFIER = re.compile(r"^[A-Za-z0-9_-]+$")


class LexiconLoadError(RuntimeError):
    """术语库文件无法安全加载或不符合基础结构。"""


class JsonLexiconProvider(LexiconProvider):
    """从仓库内版本化 JSON 文件加载术语库。"""

    def __init__(self, root_path: Path = DEFAULT_LEXICON_ROOT) -> None:
        self.root_path = root_path.resolve()

    def load_common(self, version: str | None = None) -> LexiconManifest:
        """加载公共术语库。"""
        return self._load_manifest(
            self.root_path / "common.json",
            expected_scope=LexiconScope.COMMON,
            expected_version=version,
        )

    def load_domain(self, domain: str, version: str | None = None) -> LexiconManifest:
        """按安全业务域标识加载业务术语库。"""
        safe_domain = self._validate_file_identifier(domain, "业务域")
        return self._load_manifest(
            self.root_path / f"{safe_domain}.json",
            expected_scope=LexiconScope.DOMAIN,
            expected_version=version,
        )

    def load_project(
        self, project_id: str, version: str | None = None
    ) -> LexiconManifest | None:
        """加载项目术语库；文件不存在表示项目尚未配置专属词库。"""
        safe_project_id = self._validate_file_identifier(str(project_id), "项目")
        path = self.root_path / "projects" / f"{safe_project_id}.json"
        if not path.is_file():
            return None
        return self._load_manifest(
            path,
            expected_scope=LexiconScope.PROJECT,
            expected_version=version,
            expected_scope_id=safe_project_id,
        )

    def _load_manifest(
        self,
        path: Path,
        *,
        expected_scope: LexiconScope,
        expected_version: str | None,
        expected_scope_id: str | None = None,
    ) -> LexiconManifest:
        resolved_path = path.resolve()
        if not resolved_path.is_relative_to(self.root_path):
            raise LexiconLoadError("术语库文件路径超出允许目录")
        if not resolved_path.is_file():
            raise LexiconLoadError(f"术语库文件不存在：{resolved_path}")

        try:
            raw_data: dict[str, Any] = json.loads(
                resolved_path.read_text(encoding="utf-8")
            )
            manifest = LexiconManifest.model_validate(raw_data)
        except (OSError, json.JSONDecodeError, ValidationError) as exc:
            raise LexiconLoadError(f"术语库文件结构无效：{resolved_path}") from exc

        if manifest.scope is not expected_scope:
            raise LexiconLoadError(
                f"术语库作用域错误：期望 {expected_scope.value}，实际 {manifest.scope.value}"
            )
        if expected_version is not None and manifest.version != expected_version:
            raise LexiconLoadError(
                f"术语库版本不匹配：期望 {expected_version}，实际 {manifest.version}"
            )
        if expected_scope_id is not None and manifest.scope_id != expected_scope_id:
            raise LexiconLoadError(
                f"项目术语库作用域标识不匹配：期望 {expected_scope_id}，实际 {manifest.scope_id}"
            )
        return manifest

    @staticmethod
    def _validate_file_identifier(value: str, label: str) -> str:
        if not _SAFE_FILE_IDENTIFIER.fullmatch(value):
            raise LexiconLoadError(f"{label}标识只能包含字母、数字、下划线和连字符")
        return value

"""不依赖外部模型的单文件结构解析器，负责生成可校验的完整详情基线。"""
from __future__ import annotations

import re
from pathlib import PurePosixPath

from app.project.context.detail_analysis.schemas import (
    ContentSlice,
    Evidence,
    FileDetailDocument,
    FileParsingEvent,
    ParserMetadata,
    PreviousVersion,
    RelatedFile,
    SourceRange,
)

_PARSER_VERSION = "deterministic-file-detail-v1"
_MAX_ANALYSIS_CHARS = 200_000

_LANGUAGE_BY_EXTENSION = {
    ".java": "java",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".vue": "vue",
    ".md": "markdown",
    ".markdown": "markdown",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".xml": "xml",
    ".sql": "sql",
    ".properties": "properties",
    ".html": "html",
    ".css": "css",
    ".scss": "scss",
    ".sh": "shell",
    ".ps1": "powershell",
}

_CONFIG_EXTENSIONS = {".json", ".yaml", ".yml", ".toml", ".xml", ".properties"}
_SOURCE_EXTENSIONS = {
    ".java", ".kt", ".kts", ".py", ".ts", ".tsx", ".js", ".jsx", ".vue", ".sql"
}

_ENTITY_PATTERNS = {
    "java": re.compile(r"\b(?:class|interface|record|enum)\s+([A-Za-z_$][\w$]*)|\b(?:public|protected|private)\s+[\w<>, ?\[\]]+\s+([A-Za-z_$][\w$]*)\s*\("),
    "kotlin": re.compile(r"\b(?:class|interface|object|fun)\s+([A-Za-z_][\w]*)"),
    "python": re.compile(r"^\s*(?:async\s+)?(?:class|def)\s+([A-Za-z_][\w]*)", re.MULTILINE),
    "typescript": re.compile(r"\b(?:class|interface|type|enum|function)\s+([A-Za-z_$][\w$]*)|\b(?:const|let)\s+([A-Za-z_$][\w$]*)\s*="),
    "javascript": re.compile(r"\b(?:class|function)\s+([A-Za-z_$][\w$]*)|\b(?:const|let)\s+([A-Za-z_$][\w$]*)\s*="),
    "vue": re.compile(r"\b(?:defineProps|defineEmits|defineStore)\s*<?|\b(?:const|function)\s+([A-Za-z_$][\w$]*)"),
}

_RISK_PATTERNS = {
    "unfinished_marker": re.compile(r"\b(?:TODO|FIXME|HACK|XXX)\b", re.IGNORECASE),
    "dynamic_code_execution": re.compile(r"\b(?:eval|exec)\s*\(|Runtime\.getRuntime\(\)\.exec|subprocess\.(?:run|Popen)"),
    "prompt_injection_suspected": re.compile(r"ignore\s+(?:all\s+)?previous\s+instructions|忽略(?:以上|之前).{0,8}指令", re.IGNORECASE),
}

_SENSITIVE_PATTERNS = {
    "private_key_material": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "hardcoded_secret_candidate": re.compile(
        r"(?i)\b(?:password|passwd|secret|api[_-]?key|access[_-]?key|token)\b\s*[:=]\s*['\"]?[^\s'\"]{6,}"
    ),
}


class FileDetailParser:
    """从文本结构中提取索引投影和完整详情；敏感内容只保留标记，不保存片段。"""

    def parse(
        self,
        event: FileParsingEvent,
        text: str,
        existing_detail: FileDetailDocument | None = None,
    ) -> FileDetailDocument:
        normalized_path = event.logical_path.replace("\\", "/")
        path = PurePosixPath(normalized_path)
        sampled_text = text[:_MAX_ANALYSIS_CHARS]
        lines = sampled_text.splitlines()
        language = self._language(path)
        module = self._module(path)
        kind = self._kind(path)
        file_type = self._file_type(module, kind, language)
        sensitive_flags = self._matched_flags(sampled_text, _SENSITIVE_PATTERNS)
        risk_flags = self._matched_flags(sampled_text, _RISK_PATTERNS)
        entities = self._entities(sampled_text, language)
        headings = self._headings(lines) if language == "markdown" else []
        keywords = self._keywords(path, module, kind, language, entities, headings)
        importance = self._importance(path, kind)
        summary = self._summary(path.name, module, kind, language)
        role = self._role(path.name, module, kind)
        content_slices = [] if sensitive_flags else self._content_slices(lines, language, keywords)
        evidence = [] if sensitive_flags else self._evidence(lines)

        return FileDetailDocument(
            id=f"file-{event.file_id}",
            project_id=event.project_id,
            file_id=event.file_id,
            schema_version="1.0.0",
            analysis_version=event.analysis_version,
            generated_at=event.occurred_at,
            updated_at=event.occurred_at,
            storage_uuid=event.storage_uuid,
            storage_name=event.storage_name,
            detail_ref=event.detail_ref,
            original_path=normalized_path,
            minio_path=event.minio_path,
            size_bytes=event.size_bytes,
            content_type=event.content_type,
            content_hash=event.content_hash.lower(),
            module=module,
            kind=kind,
            file_type=file_type,
            language=language,
            status="active",
            importance=importance,
            summary=summary,
            keywords=keywords,
            role=role,
            content_slices=content_slices,
            related_topics=keywords[:8],
            related_files=self._related_files(sampled_text),
            risk_flags=risk_flags,
            sensitive_flags=sensitive_flags,
            evidence=evidence,
            previous_versions=self._previous_versions(existing_detail, event),
            parser=ParserMetadata(
                strategy="deterministic_structure",
                parser_version=_PARSER_VERSION,
                sampled=len(text) > len(sampled_text),
                parsed_lines=len(lines),
            ),
        )

    def _language(self, path: PurePosixPath) -> str:
        return _LANGUAGE_BY_EXTENSION.get(path.suffix.lower(), "other")

    def _module(self, path: PurePosixPath) -> str:
        parts = [part for part in path.parts if part not in {".", ""}]
        if not parts:
            return "root"
        top = parts[0].lower()
        known = {
            "backend": "backend",
            "frontend": "frontend",
            "agent-service": "agent-service",
            "agent_service": "agent-service",
            "docs": "docs",
            "deploy": "deploy",
        }
        return known.get(top, top if len(parts) > 1 else "root")

    def _kind(self, path: PurePosixPath) -> str:
        lower_path = str(path).lower()
        suffix = path.suffix.lower()
        if suffix in {".md", ".markdown"}:
            return "documentation"
        if "test" in {part.lower() for part in path.parts} or re.search(r"(?:test|spec)\.", path.name.lower()):
            return "test"
        if suffix in _CONFIG_EXTENSIONS or path.name.lower() in {"dockerfile", "makefile"}:
            return "configuration"
        if any(token in lower_path for token in ("controller", "/api/", "router")):
            return "api"
        if any(token in lower_path for token in ("service", "usecase", "use_case")):
            return "service"
        if any(token in lower_path for token in ("entity", "model", "schema", "dto")):
            return "model"
        if suffix in _SOURCE_EXTENSIONS:
            return "source_code"
        return "other"

    def _file_type(self, module: str, kind: str, language: str) -> str:
        if kind == "documentation":
            return "doc"
        if kind == "configuration":
            return "config"
        if kind == "test":
            return "test"
        if language == "java":
            return "code.backend.java"
        if language in {"typescript", "javascript", "vue"}:
            return f"code.frontend.{language}"
        if language == "python" and module == "agent-service":
            return "code.agent.python"
        if kind in {"api", "service", "model", "source_code"}:
            return f"code.{module}.{language}"
        return "other"

    def _importance(self, path: PurePosixPath, kind: str) -> str:
        lower = str(path).lower()
        if any(token in lower for token in ("security", "auth", "controller", "service", "config", "application.yml")):
            return "high"
        if path.name.lower().startswith("readme") or kind in {"api", "service", "documentation"}:
            return "medium"
        if kind == "test" or path.name.lower().endswith(("lock", ".snap")):
            return "low"
        return "medium"

    def _summary(self, file_name: str, module: str, kind: str, language: str) -> str:
        kind_name = {
            "documentation": "说明文档",
            "configuration": "配置文件",
            "test": "测试文件",
            "api": "接口入口",
            "service": "业务服务",
            "model": "数据模型",
            "source_code": "源代码文件",
            "other": "项目文件",
        }[kind]
        return f"{module} 模块的{kind_name} {file_name}，主要使用 {language} 表达。"

    def _role(self, file_name: str, module: str, kind: str) -> str:
        return f"该文件在 {module} 模块中承担 {kind} 职责，为后续检索提供结构、实体与风险线索：{file_name}。"

    def _entities(self, text: str, language: str) -> list[str]:
        pattern = _ENTITY_PATTERNS.get(language)
        if pattern is None:
            return []
        values: list[str] = []
        for match in pattern.finditer(text):
            value = next((group for group in match.groups() if group), None)
            if value and value not in values:
                values.append(value[:256])
            if len(values) >= 40:
                break
        return values

    def _headings(self, lines: list[str]) -> list[str]:
        headings: list[str] = []
        for line in lines:
            match = re.match(r"^#{1,6}\s+(.+?)\s*$", line)
            if match:
                headings.append(match.group(1)[:128])
            if len(headings) >= 20:
                break
        return headings

    def _keywords(
        self,
        path: PurePosixPath,
        module: str,
        kind: str,
        language: str,
        entities: list[str],
        headings: list[str],
    ) -> list[str]:
        candidates = [path.stem, module, kind, language, *entities[:12], *headings[:8]]
        values: list[str] = []
        for candidate in candidates:
            value = re.sub(r"\s+", " ", candidate).strip(" _-./")[:64]
            if value and value.lower() not in {item.lower() for item in values}:
                values.append(value)
            if len(values) >= 20:
                break
        return values or ["project-file"]

    def _content_slices(
        self,
        lines: list[str],
        language: str,
        keywords: list[str],
    ) -> list[ContentSlice]:
        markers: list[tuple[int, str, str]] = []
        if language == "markdown":
            for line_number, line in enumerate(lines, start=1):
                match = re.match(r"^#{1,6}\s+(.+?)\s*$", line)
                if match:
                    markers.append((line_number, match.group(1), "doc"))
        else:
            pattern = _ENTITY_PATTERNS.get(language)
            if pattern is not None:
                for line_number, line in enumerate(lines, start=1):
                    match = pattern.search(line)
                    if match:
                        entity = next((group for group in match.groups() if group), "structure")
                        markers.append((line_number, entity, self._slice_type(line)))
        markers = markers[:20]
        slices: list[ContentSlice] = []
        for index, (line_number, entity, slice_type) in enumerate(markers):
            next_line = markers[index + 1][0] - 1 if index + 1 < len(markers) else min(len(lines), line_number + 40)
            end_line = max(line_number, next_line)
            slices.append(ContentSlice(
                slice_id=self._slice_id(index, entity),
                type=slice_type,
                summary=f"定义或说明 {entity} 的关键片段。",
                keywords=self._unique([entity, *keywords[:5]])[:8],
                entities=[entity],
                source_range=SourceRange(start_line=line_number, end_line=end_line),
            ))
        if not slices and lines:
            slices.append(ContentSlice(
                slice_id="file-overview",
                type="other",
                summary="文件开头的结构概览片段。",
                keywords=keywords[:8],
                entities=[],
                source_range=SourceRange(start_line=1, end_line=min(len(lines), 80)),
            ))
        return slices

    def _slice_type(self, line: str) -> str:
        lowered = line.lower()
        if any(token in lowered for token in ("controller", "router", "@getmapping", "@postmapping")):
            return "api"
        if "service" in lowered:
            return "service"
        if any(token in lowered for token in ("config", "settings", "properties")):
            return "config"
        if any(token in lowered for token in ("model", "entity", "schema", "dto")):
            return "model"
        if "test" in lowered:
            return "test"
        return "component"

    def _slice_id(self, index: int, entity: str) -> str:
        slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", entity).strip("-").lower()
        return (slug or f"slice-{index + 1}")[:128]

    def _matched_flags(self, text: str, patterns: dict[str, re.Pattern[str]]) -> list[str]:
        return [name for name, pattern in patterns.items() if pattern.search(text)]

    def _evidence(self, lines: list[str]) -> list[Evidence]:
        for line in lines:
            quote = re.sub(r"\s+", " ", line).strip()
            if quote and not quote.startswith(("//", "/*", "*")):
                return [Evidence(source="file_content", quote=quote[:300])]
        return []

    def _related_files(self, text: str) -> list[RelatedFile]:
        pattern = re.compile(r"(?:from\s+|import\s+(?:.+?\s+from\s+)?)[\"'](\.{1,2}/[^\"']+)[\"']")
        files: list[RelatedFile] = []
        for match in pattern.finditer(text):
            path = match.group(1)
            if path not in {item.path for item in files}:
                files.append(RelatedFile(path=path[:512], relation="other"))
            if len(files) >= 20:
                break
        return files

    def _unique(self, values: list[str]) -> list[str]:
        result: list[str] = []
        for value in values:
            if value and value.lower() not in {item.lower() for item in result}:
                result.append(value[:64])
        return result

    def _previous_versions(
        self,
        existing_detail: FileDetailDocument | None,
        event: FileParsingEvent,
    ) -> list[PreviousVersion]:
        if existing_detail is None or existing_detail.content_hash.lower() == event.content_hash.lower():
            return existing_detail.previous_versions if existing_detail is not None else []
        current = PreviousVersion(
            content_hash=existing_detail.content_hash,
            role=existing_detail.role,
            changed_at=existing_detail.updated_at,
            reason="文件内容或路径变化后重新生成详情",
        )
        return [current, *existing_detail.previous_versions][:20]

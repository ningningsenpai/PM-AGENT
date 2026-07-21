from __future__ import annotations

from pathlib import Path

from .base import FileParser
from .docx import DocxFileParser
from .text import CodeFileParser, ConfigFileParser, MarkdownFileParser, TextFileParser

__all__ = ["FileParserFactory"]

_CODE_LANGUAGES = {
    "py": "python",
    "pyi": "python",
    "pyx": "python",
    "python": "python",
    "java": "java",
    "kt": "kotlin",
    "kts": "kotlin",
    "kotlin": "kotlin",
    "scala": "scala",
    "groovy": "groovy",
    "go": "go",
    "rs": "rust",
    "rust": "rust",
    "c": "c",
    "h": "c",
    "cc": "cpp",
    "cpp": "cpp",
    "cxx": "cpp",
    "hpp": "cpp",
    "cs": "csharp",
    "csharp": "csharp",
    "fs": "fsharp",
    "fsx": "fsharp",
    "js": "javascript",
    "mjs": "javascript",
    "cjs": "javascript",
    "jsx": "javascript",
    "javascript": "javascript",
    "ts": "typescript",
    "tsx": "typescript",
    "typescript": "typescript",
    "vue": "vue",
    "svelte": "svelte",
    "php": "php",
    "rb": "ruby",
    "ruby": "ruby",
    "swift": "swift",
    "dart": "dart",
    "lua": "lua",
    "r": "r",
    "sh": "shell",
    "bash": "shell",
    "zsh": "shell",
    "fish": "shell",
    "ps1": "powershell",
    "powershell": "powershell",
    "bat": "batch",
    "cmd": "batch",
    "sql": "sql",
    "graphql": "graphql",
    "gql": "graphql",
    "html": "html",
    "htm": "html",
    "css": "css",
    "scss": "scss",
    "sass": "sass",
    "less": "less",
}

_CONFIG_LANGUAGES = {
    "json": "json",
    "json5": "json",
    "jsonc": "json",
    "yaml": "yaml",
    "yml": "yaml",
    "toml": "toml",
    "xml": "xml",
    "ini": "ini",
    "cfg": "config",
    "conf": "config",
    "properties": "properties",
    "env": "dotenv",
    "gradle": "gradle",
    "lock": "lock",
    "editorconfig": "editorconfig",
}

_MARKDOWN_TYPES = {"md", "markdown", "mdx"}
_TEXT_TYPES = {
    "text",
    "txt",
    "log",
    "csv",
    "tsv",
    "adoc",
    "rst",
    "tex",
    "gitignore",
    "gitattributes",
    "dockerfile",
    "makefile",
}
_DOCX_TYPES = {"doc", "docx", "word"}
_UNSUPPORTED_BINARY_TYPES = {
    "legacy-doc",
    "pdf",
    "xls",
    "xlsx",
    "ppt",
    "pptx",
    "zip",
    "rar",
    "7z",
    "tar",
    "gz",
    "jar",
    "war",
    "class",
    "exe",
    "dll",
    "so",
    "png",
    "jpg",
    "jpeg",
    "gif",
    "webp",
    "bmp",
}
_MIME_TYPE_ALIASES = {
    "text/plain": "text",
    "text/markdown": "markdown",
    "text/csv": "csv",
    "text/html": "html",
    "text/css": "css",
    "text/xml": "xml",
    "text/x-python": "python",
    "text/x-java-source": "java",
    "application/json": "json",
    "application/xml": "xml",
    "application/yaml": "yaml",
    "application/x-yaml": "yaml",
    "application/sql": "sql",
    "application/msword": "legacy-doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/pdf": "pdf",
}
_GENERIC_TYPES = {"", "code", "config", "text", "doc", "application/octet-stream"}


class FileParserFactory:
    """根据业务类型、MIME 类型或文件名选择解析器。"""

    def get_parser(
        self,
        file_type: str,
        file_name: str | None = None,
    ) -> FileParser:
        type_key = self._normalize_type(file_type)
        file_key = self._normalize_type(file_name or "")

        if file_key == "doc":
            raise ValueError("不支持旧版 DOC 文件，请先转换为 DOCX")
        if file_key in _UNSUPPORTED_BINARY_TYPES and file_key != "docx":
            raise ValueError(f"暂不支持解析 {file_key.upper()} 文件")

        selected_key = type_key
        if type_key in _GENERIC_TYPES and file_key:
            selected_key = file_key

        if selected_key in _CODE_LANGUAGES:
            return CodeFileParser(_CODE_LANGUAGES[selected_key])
        if selected_key in _MARKDOWN_TYPES:
            return MarkdownFileParser()
        if selected_key in _CONFIG_LANGUAGES:
            return ConfigFileParser(_CONFIG_LANGUAGES[selected_key])
        if selected_key in _TEXT_TYPES:
            return TextFileParser()
        if type_key in _DOCX_TYPES or selected_key == "docx":
            return DocxFileParser()
        if selected_key == "code":
            return CodeFileParser("unknown")
        if selected_key == "config":
            return ConfigFileParser()
        if selected_key in _UNSUPPORTED_BINARY_TYPES:
            raise ValueError(f"暂不支持解析 {selected_key.upper()} 文件")
        if "/" in selected_key:
            raise ValueError(f"暂不支持解析媒体类型 {file_type}")
        return TextFileParser()

    def _normalize_type(self, value: str) -> str:
        normalized = value.strip().lower()
        if normalized in _MIME_TYPE_ALIASES:
            return _MIME_TYPE_ALIASES[normalized]
        if normalized.startswith("code."):
            return normalized.rsplit(".", maxsplit=1)[-1]
        if "/" in normalized:
            return normalized

        path = Path(normalized)
        if path.suffix:
            return path.suffix.lstrip(".")
        return normalized.lstrip(".")

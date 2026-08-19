"""发送文件内容给模型前的确定性敏感信息处理。"""

from __future__ import annotations

from dataclasses import dataclass
import re

__all__ = [
    "SensitiveContentBlockedError",
    "SensitiveContentResult",
    "sanitize_sensitive_content",
]


class SensitiveContentBlockedError(ValueError):
    """文件包含不能发送给模型的凭据材料。"""


@dataclass(frozen=True, slots=True)
class SensitiveContentResult:
    content: str
    flags: list[dict[str, object]]


_PRIVATE_KEY_BEGIN = re.compile(
    r"-----BEGIN [^-\r\n]*PRIVATE KEY(?: BLOCK)?-----",
    re.IGNORECASE,
)
_CREDENTIAL_NAME = (
    r"[A-Za-z0-9_.-]*(?:password|passwd|pwd|secret|api[_-]?key|"
    r"access[_-]?key|client[_-]?secret|token|authorization)"
)
_QUOTED_ASSIGNMENT = re.compile(
    rf"(?P<prefix>['\"]?\b(?:{_CREDENTIAL_NAME})\b['\"]?\s*[:=]\s*)"
    r"(?P<quote>['\"])(?P<value>.*?)(?P=quote)",
    re.IGNORECASE,
)
_PLAIN_ASSIGNMENT = re.compile(
    rf"(?P<prefix>['\"]?\b(?:{_CREDENTIAL_NAME})\b['\"]?\s*[:=]\s*)"
    r"(?P<value>\[已脱敏\]|[^\s,;}\"']+)",
    re.IGNORECASE,
)
_BEARER_TOKEN = re.compile(
    r"\bBearer\s+[A-Za-z0-9._~+/=-]{8,}",
    re.IGNORECASE,
)
_URI_PASSWORD = re.compile(
    r"(?P<prefix>[a-z][a-z0-9+.-]*://[^\s:/@]+:)(?P<value>[^\s/@]+)(?=@)",
    re.IGNORECASE,
)
_KNOWN_TOKEN = re.compile(
    r"\b(?:"
    r"gh[pousr]_[A-Za-z0-9]{20,}|"
    r"github_pat_[A-Za-z0-9_]{20,}|"
    r"glpat-[A-Za-z0-9_-]{16,}|"
    r"xox[baprs]-[A-Za-z0-9-]{10,}|"
    r"sk-[A-Za-z0-9_-]{16,}|"
    r"(?:sk|pk)_live_[A-Za-z0-9]{16,}|"
    r"AKIA[A-Z0-9]{16}"
    r")\b"
)
_REDACTED = "[已脱敏]"


def sanitize_sensitive_content(content: str) -> SensitiveContentResult:
    """阻断私钥并替换常见明文凭据，避免原始秘密进入 Prompt。"""
    if _PRIVATE_KEY_BEGIN.search(content):
        raise SensitiveContentBlockedError("文件包含私钥内容")

    redacted_count = 0

    def replace_quoted(match: re.Match[str]) -> str:
        nonlocal redacted_count
        redacted_count += 1
        return f"{match.group('prefix')}{match.group('quote')}{_REDACTED}{match.group('quote')}"

    def replace_plain(match: re.Match[str]) -> str:
        nonlocal redacted_count
        if match.group("value") == _REDACTED:
            return match.group(0)
        redacted_count += 1
        return f"{match.group('prefix')}{_REDACTED}"

    def replace_fixed(match: re.Match[str]) -> str:
        nonlocal redacted_count
        redacted_count += 1
        return _REDACTED

    def replace_uri(match: re.Match[str]) -> str:
        nonlocal redacted_count
        redacted_count += 1
        return f"{match.group('prefix')}{_REDACTED}"

    sanitized = _BEARER_TOKEN.sub(
        lambda match: f"Bearer {replace_fixed(match)}",
        content,
    )
    sanitized = _URI_PASSWORD.sub(replace_uri, sanitized)
    sanitized = _KNOWN_TOKEN.sub(replace_fixed, sanitized)
    sanitized = _QUOTED_ASSIGNMENT.sub(replace_quoted, sanitized)
    sanitized = _PLAIN_ASSIGNMENT.sub(replace_plain, sanitized)
    flags: list[dict[str, object]] = []
    if redacted_count:
        flags.append(
            {
                "type": "credential_redacted",
                "count": redacted_count,
                "message": "模型输入前已脱敏明文凭据",
            }
        )
    return SensitiveContentResult(content=sanitized, flags=flags)

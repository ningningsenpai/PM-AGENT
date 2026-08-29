"""原项目文件证据读取、截取与敏感处理。"""

from __future__ import annotations

from app.core.errors import AppException
from app.input_context.retrieval.candidate import RetrievalCandidate
from app.input_context.retrieval.policy import RetrievalPolicy
from app.input_context.retrieval.schemas import RetrievalEvidence
from app.input_context.retrieval.snapshot import ProjectSnapshot, ProjectSnapshotReader
from app.project_context.file_detail.extraction import FileContentExtractionService
from app.project_context.file_detail.sensitive_content import (
    SensitiveContentBlockedError,
    sanitize_sensitive_content,
)


class RawEvidenceLoader:
    """在严格配额内读取可信候选对应的原文件证据。"""

    def __init__(
        self,
        reader: ProjectSnapshotReader,
        extraction: FileContentExtractionService,
        policy: RetrievalPolicy,
    ) -> None:
        self._reader = reader
        self._extraction = extraction
        self._policy = policy

    async def hydrate(
        self,
        selected: list[RetrievalCandidate],
        snapshot: ProjectSnapshot,
        warnings: list[str],
    ) -> None:
        remaining_bytes = self._policy.max_raw_evidence_bytes
        hydrated = 0
        for candidate in selected:
            if hydrated >= self._policy.max_raw_files or remaining_bytes <= 0:
                break
            entry = candidate.file_entry
            if entry is None:
                continue
            try:
                source_bytes = await self._reader.read_bytes(
                    self._reader.project_file_location(snapshot, entry.minio_path)
                )
                extracted = await self._extraction.extract_from_bytes(
                    source_bytes,
                    entry.file_type or entry.content_type,
                    entry.file_name,
                )
                sanitized = sanitize_sensitive_content(extracted.get("text", ""))
            except SensitiveContentBlockedError:
                warnings.append(
                    f"原文件包含禁止进入模型的敏感内容：{entry.logical_path}"
                )
                continue
            except (AppException, OSError, UnicodeDecodeError, ValueError):
                warnings.append(f"原文件无法读取或提取：{entry.logical_path}")
                continue

            source_text, start_line, end_line = self._source_slice(
                sanitized.text,
                candidate.source_range,
            )
            source_text = self._truncate_utf8(source_text, remaining_bytes)
            if not source_text.strip():
                continue
            remaining_bytes -= len(source_text.encode("utf-8"))
            candidate.source_type = "source_file"
            candidate.evidence.insert(
                0,
                RetrievalEvidence(
                    text=source_text,
                    logical_path=entry.logical_path,
                    start_line=start_line,
                    end_line=end_line,
                    redacted=bool(sanitized.flags),
                ),
            )
            hydrated += 1

    @staticmethod
    def _source_slice(
        text: str,
        source_range: tuple[int, int] | None,
    ) -> tuple[str, int, int]:
        lines = text.splitlines()
        if not lines:
            return "", 1, 1
        start_line = 1
        end_line = min(len(lines), 100)
        if source_range is not None:
            raw_start, raw_end = source_range
            start_line = max(1, raw_start)
            end_line = min(len(lines), max(start_line, raw_end), start_line + 99)
        numbered = [
            f"{line_number}: {lines[line_number - 1]}"
            for line_number in range(start_line, end_line + 1)
        ]
        return "\n".join(numbered), start_line, end_line

    @staticmethod
    def _truncate_utf8(text: str, max_bytes: int) -> str:
        encoded = text.encode("utf-8")
        if len(encoded) <= max_bytes:
            return text
        return encoded[:max_bytes].decode("utf-8", errors="ignore")

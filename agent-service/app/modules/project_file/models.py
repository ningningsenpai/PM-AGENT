"""项目文件持久化模型。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base, TimestampMixin
from app.modules.project_file.domain import (
    FileBusinessType,
    ProjectFileStatus,
    ProjectFileUploadStatus,
)


class ProjectFile(TimestampMixin, Base):
    __tablename__ = "pm_project_file"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "business_code",
            "path_hash",
            name="uk_project_file_path",
        ),
        UniqueConstraint("object_key", name="uk_project_file_object_key"),
        UniqueConstraint(
            "project_id",
            "business_code",
            "storage_name",
            name="uk_project_file_storage_name",
        ),
        UniqueConstraint(
            "project_id",
            "storage_uuid",
            name="uk_project_file_storage_uuid",
        ),
        CheckConstraint(
            "business_code IN ('project', 'user', 'system')",
            name="ck_project_file_business",
        ),
        CheckConstraint(
            "status IN ('uploading', 'active', 'updating', 'upload_failed', "
            "'verify_required', 'missing', 'deleting', 'delete_failed')",
            name="ck_project_file_status",
        ),
        CheckConstraint(
            "upload_status IN ('not_uploaded', 'success', 'retrying', 'failed')",
            name="ck_project_file_upload_status",
        ),
        CheckConstraint(
            "upload_attempts >= 0",
            name="ck_project_file_upload_attempts",
        ),
        CheckConstraint(
            "parse_attempts >= 0",
            name="ck_project_file_parse_attempts",
        ),
        Index(
            "idx_project_file_content",
            "project_id",
            "business_code",
            "content_hash",
        ),
        Index(
            "idx_project_file_status",
            "project_id",
            "business_code",
            "status",
        ),
        Index("idx_project_file_parse", "project_id", "parse_attempts"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    project_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("pm_project.id", ondelete="CASCADE"),
        nullable=False,
    )
    business_code: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=FileBusinessType.PROJECT.value,
    )
    relative_path: Mapped[str] = mapped_column(String(512), nullable=False)
    path_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    extension: Mapped[str | None] = mapped_column(String(32), nullable=True)
    storage_uuid: Mapped[str] = mapped_column(String(16), nullable=False)
    storage_name: Mapped[str] = mapped_column(String(255), nullable=False)
    object_key: Mapped[str] = mapped_column(String(512), nullable=False)
    minio_path: Mapped[str] = mapped_column(String(512), nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source_mtime_ms: Mapped[int] = mapped_column(BigInteger, nullable=False)
    quick_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=ProjectFileStatus.UPLOADING.value,
    )
    upload_status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=ProjectFileUploadStatus.NOT_UPLOADED.value,
    )
    upload_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    parse_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    detail_ref: Mapped[str | None] = mapped_column(String(512), nullable=True)
    analysis_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    module: Mapped[str | None] = mapped_column(String(128), nullable=True)
    kind: Mapped[str | None] = mapped_column(String(64), nullable=True)
    file_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    language: Mapped[str | None] = mapped_column(String(64), nullable=True)
    importance: Mapped[str | None] = mapped_column(String(16), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    keywords: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    last_error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    last_failed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    lock_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

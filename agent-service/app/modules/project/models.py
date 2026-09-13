"""项目持久化模型。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Computed,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base, TimestampMixin
from app.modules.project.domain import ProjectRecordStatus, ProjectStatus


class Project(TimestampMixin, Base):
    __tablename__ = "pm_project"
    __table_args__ = (
        UniqueConstraint(
            "owner_user_id",
            "enabled_project_name",
            name="uk_project_owner_enabled_name",
        ),
        CheckConstraint(
            "status IN ('initializing', 'active', 'init_failed')",
            name="ck_project_status",
        ),
        CheckConstraint(
            "record_status IN ('enabled', 'disabled')",
            name="ck_project_record_status",
        ),
        CheckConstraint(
            "revision >= published_revision AND published_revision >= 0",
            name="ck_project_revision_order",
        ),
        Index("idx_project_owner_status", "owner_user_id", "status"),
        Index(
            "idx_project_owner_record_status",
            "owner_user_id",
            "record_status",
        ),
        Index("idx_project_record_purge", "record_status", "purge_after"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=False,
    )
    owner_user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("pm_user.id", ondelete="CASCADE"),
        nullable=False,
    )
    project_name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=ProjectStatus.INITIALIZING.value,
    )
    record_status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=ProjectRecordStatus.ENABLED.value,
    )
    enabled_project_name: Mapped[str | None] = mapped_column(
        String(128),
        Computed(
            "CASE WHEN record_status = 'enabled' THEN project_name ELSE NULL END",
            persisted=True,
        ),
        nullable=True,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    purge_after: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    published_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

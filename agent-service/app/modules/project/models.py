"""项目持久化模型。"""
from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base, TimestampMixin
from app.modules.project.domain import ProjectStatus


class Project(TimestampMixin, Base):
    __tablename__ = "pm_project"
    __table_args__ = (
        UniqueConstraint(
            "owner_user_id",
            "project_name",
            name="uk_project_owner_name",
        ),
        CheckConstraint(
            "status IN ('initializing', 'active', 'init_failed')",
            name="ck_project_status",
        ),
        Index("idx_project_owner_status", "owner_user_id", "status"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
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

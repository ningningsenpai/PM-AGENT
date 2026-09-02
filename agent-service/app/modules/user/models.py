"""用户持久化模型。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base, TimestampMixin
from app.modules.user.domain import UserStatus


class User(TimestampMixin, Base):
    __tablename__ = "pm_user"
    __table_args__ = (
        UniqueConstraint("username", name="uk_user_username"),
        UniqueConstraint("email", name="uk_user_email"),
        CheckConstraint(
            "status IN ('enabled', 'disabled')",
            name="ck_user_status",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=False,
    )
    username: Mapped[str] = mapped_column(String(64), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=UserStatus.ENABLED.value,
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

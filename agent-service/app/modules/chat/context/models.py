"""职责子包的持久化实体；保留既有表名、字段和索引。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base, TimestampMixin

from .._persistence import ID


class AgentContextScope(TimestampMixin, Base):
    __tablename__ = "agent_context_scope"
    scope_key: Mapped[str] = mapped_column(String(100), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("pm_user.id", ondelete="CASCADE")
    )
    project_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("pm_project.id", ondelete="CASCADE")
    )
    version: Mapped[int] = mapped_column(Integer, default=0)
    published_version: Mapped[int] = mapped_column(Integer, default=0)
    snapshot_error: Mapped[str | None] = mapped_column(String(200))


class AgentContextEntry(TimestampMixin, Base):
    __tablename__ = "agent_context_entry"
    __table_args__ = (
        UniqueConstraint(
            "scope_key", "kind", "canonical_key", name="uk_entry_scope_kind_key"
        ),
        Index("ix_entry_scope_status", "user_id", "project_id", "status", "expires_at"),
    )
    id: Mapped[int] = mapped_column(ID, primary_key=True, autoincrement=False)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("pm_user.id", ondelete="CASCADE")
    )
    project_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("pm_project.id", ondelete="CASCADE")
    )
    scope_key: Mapped[str] = mapped_column(
        String(100), ForeignKey("agent_context_scope.scope_key", ondelete="CASCADE")
    )
    kind: Mapped[str] = mapped_column(String(24))
    canonical_key: Mapped[str] = mapped_column(String(64))
    content: Mapped[str] = mapped_column(Text)
    attributes: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    version: Mapped[int] = mapped_column(Integer, default=1)
    source_message_id: Mapped[int | None] = mapped_column(BigInteger)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime)


class AgentContextChange(TimestampMixin, Base):
    __tablename__ = "agent_context_change"
    __table_args__ = (Index("ix_change_entry_version", "entry_id", "version"),)
    id: Mapped[int] = mapped_column(ID, primary_key=True, autoincrement=False)
    entry_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("agent_context_entry.id", ondelete="CASCADE")
    )
    version: Mapped[int] = mapped_column(Integer)
    before: Mapped[dict] = mapped_column(JSON, default=dict)
    after: Mapped[dict] = mapped_column(JSON)
    reason: Mapped[str] = mapped_column(Text)
    source_message_id: Mapped[int | None] = mapped_column(BigInteger)

"""职责子包的持久化实体；保留既有表名、字段和索引。"""

from __future__ import annotations

from sqlalchemy import (
    JSON,
    BigInteger,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base, TimestampMixin

from .._persistence import ID


class AgentRun(TimestampMixin, Base):
    __tablename__ = "agent_run"
    __table_args__ = (
        UniqueConstraint("user_id", "operation", "request_key", name="uk_run_request"),
        Index("ix_run_conversation_status", "conversation_id", "status"),
    )
    id: Mapped[int] = mapped_column(ID, primary_key=True, autoincrement=False)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("pm_user.id", ondelete="CASCADE")
    )
    project_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("pm_project.id", ondelete="CASCADE")
    )
    conversation_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("agent_conversation.id", ondelete="CASCADE")
    )
    operation: Mapped[str] = mapped_column(String(32))
    request_key: Mapped[str] = mapped_column(String(128))
    request_hash: Mapped[str] = mapped_column(String(64))
    trace_id: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(16), default="running")
    events: Mapped[list] = mapped_column(JSON, default=list)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text)

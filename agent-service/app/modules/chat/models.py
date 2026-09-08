"""会话、学习上下文及模型运行的持久化模型。"""

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
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base, TimestampMixin

ID = BigInteger().with_variant(Integer, "sqlite")


class AgentConversation(TimestampMixin, Base):
    __tablename__ = "agent_conversation"
    __table_args__ = (Index("ix_conversation_owner_project", "user_id", "project_id"),)
    id: Mapped[int] = mapped_column(ID, primary_key=True, autoincrement=False)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("pm_user.id", ondelete="CASCADE")
    )
    project_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("pm_project.id", ondelete="CASCADE")
    )
    title: Mapped[str] = mapped_column(String(128))
    learned_message_id: Mapped[int] = mapped_column(BigInteger, default=0)
    active_run_id: Mapped[int | None] = mapped_column(BigInteger)
    busy_until: Mapped[datetime | None] = mapped_column(DateTime)


class AgentMessage(TimestampMixin, Base):
    __tablename__ = "agent_message"
    __table_args__ = (Index("ix_message_conversation_id", "conversation_id", "id"),)
    id: Mapped[int] = mapped_column(ID, primary_key=True, autoincrement=False)
    conversation_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("agent_conversation.id", ondelete="CASCADE")
    )
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text().with_variant(LONGTEXT, "mysql"))
    run_id: Mapped[int] = mapped_column(BigInteger)
    # 仅服务端生成的完整协议组可用于跨轮恢复，客户端不能提交工具角色。
    protocol: Mapped[list] = mapped_column(JSON, default=list)


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

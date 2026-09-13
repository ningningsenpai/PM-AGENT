"""职责子包的持久化实体；保留既有表名、字段和索引。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base, TimestampMixin

from .._persistence import ID


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

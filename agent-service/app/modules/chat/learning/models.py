"""显式学习草稿的数据库实体。"""

from __future__ import annotations

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base, TimestampMixin

from .._persistence import ID


class AgentLearningDraft(TimestampMixin, Base):
    __tablename__ = "agent_learning_draft"
    __table_args__ = (
        CheckConstraint(
            "state IN ('pending','updating','partial','applied','discarded')",
            name="ck_learning_draft_state",
        ),
        Index(
            "ix_learning_draft_owner_project_state",
            "user_id",
            "project_id",
            "state",
            "id",
        ),
        Index("ix_learning_draft_conversation", "conversation_id", "id"),
    )

    id: Mapped[int] = mapped_column(ID, primary_key=True, autoincrement=False)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("pm_user.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("pm_project.id", ondelete="CASCADE"), nullable=False
    )
    conversation_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("agent_conversation.id", ondelete="CASCADE"),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    lock_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    state: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

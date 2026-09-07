"""项目报告持久化模型。"""

from sqlalchemy import JSON, BigInteger, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.mysql import LONGTEXT

from app.infrastructure.database import Base, TimestampMixin

ID = BigInteger().with_variant(Integer, "sqlite")


class ProjectReport(TimestampMixin, Base):
    __tablename__ = "pm_report"
    __table_args__ = (Index("ix_report_project_kind", "project_id", "kind", "id"),)
    id: Mapped[int] = mapped_column(ID, primary_key=True, autoincrement=False)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("pm_user.id", ondelete="CASCADE")
    )
    project_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("pm_project.id", ondelete="CASCADE")
    )
    run_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("agent_run.id", ondelete="CASCADE")
    )
    kind: Mapped[str] = mapped_column(String(16))
    markdown: Mapped[str] = mapped_column(Text().with_variant(LONGTEXT, "mysql"))
    source_versions: Mapped[dict] = mapped_column(JSON)
    evidence: Mapped[list] = mapped_column(JSON)

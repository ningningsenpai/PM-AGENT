"""增加项目延迟物理清理时间。

Revision ID: 20260903_02
Revises: 20260903_01
Create Date: 2026-09-03
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260903_02"
down_revision: str | Sequence[str] | None = "20260903_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "pm_project",
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "pm_project",
        sa.Column("purge_after", sa.DateTime(), nullable=True),
    )
    op.execute(
        sa.text(
            "UPDATE pm_project "
            "SET deleted_at = updated_at, "
            "purge_after = DATE_ADD(updated_at, INTERVAL 30 DAY) "
            "WHERE record_status = 'disabled'"
        )
    )
    op.create_index(
        "idx_project_record_purge",
        "pm_project",
        ["record_status", "purge_after"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_project_record_purge", table_name="pm_project")
    op.drop_column("pm_project", "purge_after")
    op.drop_column("pm_project", "deleted_at")

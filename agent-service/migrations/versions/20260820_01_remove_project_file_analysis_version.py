"""删除项目文件分析版本字段。

Revision ID: 20260820_01
Revises: 20260724_01
Create Date: 2026-08-20
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260820_01"
down_revision = "20260724_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("pm_project_file", "analysis_version")


def downgrade() -> None:
    op.add_column(
        "pm_project_file",
        sa.Column("analysis_version", sa.String(length=64), nullable=True),
    )

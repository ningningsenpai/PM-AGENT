"""为项目增加惰性删除状态。

Revision ID: 20260902_01
Revises: 20260820_01
Create Date: 2026-09-02
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260902_01"
down_revision = "20260820_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "pm_project",
        sa.Column(
            "record_status",
            sa.String(length=16),
            server_default="active",
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_project_record_status",
        "pm_project",
        "record_status IN ('active', 'inactive')",
    )
    op.create_index(
        "idx_project_owner_record_status",
        "pm_project",
        ["owner_user_id", "record_status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_project_owner_record_status", table_name="pm_project")
    op.drop_constraint(
        "ck_project_record_status",
        "pm_project",
        type_="check",
    )
    op.drop_column("pm_project", "record_status")
